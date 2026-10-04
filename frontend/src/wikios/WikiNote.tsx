// Ported from wiki-os src/client/routes/wiki-route.tsx (MIT).
// react-router plumbing (loader/useLoaderData/useNavigate/useRevalidator/
// redirect) is replaced by props + in-component fetching: the note path comes
// from the WikiTab sub-view state, navigation happens through callbacks, and
// reloading after a person-override is an explicit refetch.

import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";

import { useWikiConfig } from "./wiki-config-context";
import { getTopicColor, type TopicAliasConfig } from "./wiki-config";
import type { WikiHeading, WikiNeighbor, WikiPageData } from "./wiki-shared";
import { usePersonImage } from "./use-person-image";

import { fetchJson } from "./api";
import { WikiErrorView, messageOf, statusOf } from "./error-views";

const remarkPlugins = [remarkGfm];
const rehypePlugins = [rehypeHighlight];
const markdownComponents = {
  h1: ({ ...props }) => <h1 className="mb-4 text-3xl scroll-mt-20" {...props} />,
  h2: ({ ...props }) => <h2 className="font-display mb-3 mt-10 text-xl font-light scroll-mt-20" {...props} />,
  h3: ({ ...props }) => <h3 className="font-display mb-2 mt-7 text-lg font-light scroll-mt-20" {...props} />,
  h4: ({ ...props }) => <h4 className="mb-2 mt-5 text-base font-medium scroll-mt-20" {...props} />,
  p: ({ ...props }) => <p className="mb-4 leading-[1.8]" {...props} />,
  ul: ({ ...props }) => <ul className="mb-4 list-disc pl-6 leading-[1.8]" {...props} />,
  ol: ({ ...props }) => <ol className="mb-4 list-decimal pl-6 leading-[1.8]" {...props} />,
  li: ({ ...props }) => <li className="mb-1.5" {...props} />,
  blockquote: ({ ...props }) => <blockquote className="my-4" {...props} />,
};

export function normalizeNotePath(rawPath: string) {
  const trimmed = rawPath.trim();
  if (!trimmed) return "";
  return trimmed
    .split("/")
    .filter(Boolean)
    .map((part) => encodeURIComponent(part))
    .join("/");
}

function formatDate(timestamp: number) {
  return new Date(timestamp).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function estimateReadingTime(markdown: string) {
  const words = markdown.trim().split(/\s+/).length;
  return Math.max(1, Math.round(words / 200));
}

function wordCount(markdown: string) {
  return markdown.trim().split(/\s+/).length;
}

/* ── Table of Contents ── */

function TableOfContents({
  headings,
  activeId,
}: {
  headings: WikiHeading[];
  activeId: string | null;
}) {
  if (headings.length === 0) return null;

  return (
    <nav className="toc space-y-0.5">
      <p className="mb-3 text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
        On this page
      </p>
      {headings.map((h) => (
        <a
          key={h.id}
          href={`#${h.id}`}
          onClick={(e) => {
            e.preventDefault();
            document.getElementById(h.id)?.scrollIntoView({ behavior: "smooth" });
          }}
          className={`toc-item block text-[13px] leading-snug transition-colors duration-150 ${
            h.level === 3 ? "pl-3" : h.level >= 4 ? "pl-6" : ""
          } ${
            activeId === h.id
              ? "text-[var(--foreground)] font-medium"
              : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
          }`}
          style={{ paddingTop: "0.3rem", paddingBottom: "0.3rem" }}
        >
          {h.text}
        </a>
      ))}
    </nav>
  );
}

function useActiveHeading(headings: WikiHeading[], scrollRef: React.RefObject<HTMLDivElement | null>) {
  const [activeId, setActiveId] = useState<string | null>(headings[0]?.id ?? null);
  const observer = useRef<IntersectionObserver | null>(null);

  const observe = useCallback(() => {
    observer.current?.disconnect();

    const ids = headings.map((h) => h.id);
    const elements = ids
      .map((id) => document.getElementById(id))
      .filter((el): el is HTMLElement => el !== null);

    if (elements.length === 0) return;

    // Track which headings have scrolled past the top of the scroll container
    observer.current = new IntersectionObserver(
      () => {
        const allHeadingEls = ids
          .map((id) => document.getElementById(id))
          .filter((el): el is HTMLElement => el !== null);

        let current = allHeadingEls[0]?.id ?? null;
        for (const el of allHeadingEls) {
          if (el.getBoundingClientRect().top <= 100) {
            current = el.id;
          }
        }
        setActiveId(current);
      },
      { root: scrollRef.current, rootMargin: "-60px 0px -80% 0px", threshold: [0, 1] },
    );

    for (const el of elements) {
      observer.current.observe(el);
    }
  }, [headings, scrollRef]);

  useEffect(() => {
    const timer = setTimeout(observe, 100);
    return () => {
      clearTimeout(timer);
      observer.current?.disconnect();
    };
  }, [observe]);

  // Also track on scroll for short pages (the scroll container, not window)
  useEffect(() => {
    const container = scrollRef.current;
    if (!container) return;

    const handleScroll = () => {
      const ids = headings.map((h) => h.id);
      const elements = ids
        .map((id) => document.getElementById(id))
        .filter((el): el is HTMLElement => el !== null);

      if (elements.length === 0) return;

      let current = elements[0]?.id ?? null;
      for (const el of elements) {
        if (el.getBoundingClientRect().top <= 100) {
          current = el.id;
        }
      }
      setActiveId(current);
    };

    container.addEventListener("scroll", handleScroll, { passive: true });
    return () => container.removeEventListener("scroll", handleScroll);
  }, [headings, scrollRef]);

  return activeId;
}

/* ── Markdown section splitting ── */

interface ParsedLink {
  label: string;
  href: string;
}

function parseMarkdownLinks(section: string): ParsedLink[] {
  const linkRegex = /\[([^\]]+)\]\(([^)]+)\)/g;
  const links: ParsedLink[] = [];
  let match;
  while ((match = linkRegex.exec(section)) !== null) {
    links.push({ label: match[1], href: match[2] });
  }
  return links;
}

function splitContentSections(markdown: string) {
  const relatedMatch = markdown.match(/\n## Related Concepts\n([\s\S]*?)(?=\n## |\s*$)/);
  const sourceMatch = markdown.match(/\n## Source Notes\n([\s\S]*?)(?=\n## |\s*$)/);

  let mainContent = markdown;
  if (relatedMatch) {
    mainContent = mainContent.replace(`\n## Related Concepts\n${relatedMatch[1]}`, "");
  }
  if (sourceMatch) {
    mainContent = mainContent.replace(`\n## Source Notes\n${sourceMatch[1]}`, "");
  }

  return {
    mainContent: mainContent.trimEnd(),
    relatedLinks: relatedMatch ? parseMarkdownLinks(relatedMatch[1]) : [],
    sourceLinks: sourceMatch ? parseMarkdownLinks(sourceMatch[1]) : [],
    sourceRaw: sourceMatch?.[1]?.trim() ?? "",
  };
}

function wikiSlugFromHref(href: string): string | null {
  const trimmed = href.trim();
  if (trimmed.startsWith("/wiki/")) {
    return trimmed.slice("/wiki/".length).replace(/\/$/, "");
  }
  if (/\.md$/i.test(trimmed)) {
    return trimmed.replace(/\.md$/i, "").replace(/^\.\//, "");
  }
  return null;
}

/* ── Mini Neighborhood Graph ── */

function miniColor(
  cats: string[],
  aliases: Record<string, TopicAliasConfig>,
): string {
  for (const category of cats) {
    return getTopicColor(category, aliases);
  }

  return "#666";
}

interface MiniNode {
  x: number;
  y: number;
  slug: string;
  title: string;
  color: string;
  size: number;
  isCenter: boolean;
}

function computeScatteredLayout(
  currentTitle: string,
  currentCategories: string[],
  neighbors: WikiNeighbor[],
  w: number,
  h: number,
  aliases: Record<string, TopicAliasConfig>,
): MiniNode[] {
  const displayed = neighbors.slice(0, 14);
  const cx = w / 2;
  const cy = h / 2;
  const nodes: MiniNode[] = [];

  // Center node
  nodes.push({
    x: cx, y: cy,
    slug: "", title: currentTitle,
    color: miniColor(currentCategories, aliases),
    size: 7, isCenter: true,
  });

  // Scatter neighbors using a seeded pseudo-random for consistency
  const spread = Math.min(w, h) * 0.38;
  for (let i = 0; i < displayed.length; i++) {
    const n = displayed[i];
    // Golden angle distribution for natural spacing
    const angle = i * 2.399963 + 0.5; // golden angle in radians
    const r = spread * (0.4 + 0.6 * Math.sqrt((i + 1) / (displayed.length + 1)));
    // Add slight randomness seeded by title length for variety between pages
    const jitter = ((n.title.length * 7 + i * 13) % 20 - 10) * 0.02;
    nodes.push({
      x: cx + Math.cos(angle + jitter) * r,
      y: cy + Math.sin(angle + jitter) * r,
      slug: n.slug,
      title: n.title,
      color: miniColor(n.categories, aliases),
      size: Math.max(2.5, Math.min(5.5, 2.5 + Math.sqrt(n.backlinkCount) * 0.6)),
      isCenter: false,
    });
  }

  return nodes;
}

function NeighborhoodGraph({
  currentTitle,
  currentCategories,
  neighbors,
  onClickNode,
  aliases,
}: {
  currentTitle: string;
  currentCategories: string[];
  neighbors: WikiNeighbor[];
  onClickNode: (slug: string) => void;
  aliases: Record<string, TopicAliasConfig>;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);
  const layoutRef = useRef<MiniNode[]>([]);
  const dpr = typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const draw = () => {
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      if (w === 0 || h === 0) return;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      ctx.scale(dpr, dpr);

      const nodes = computeScatteredLayout(
        currentTitle,
        currentCategories,
        neighbors,
        w,
        h,
        aliases,
      );
      layoutRef.current = nodes;

      // Background (dark theme)
      ctx.fillStyle = "#131920";
      ctx.fillRect(0, 0, w, h);

      const center = nodes[0];

      // Draw edges from center to all neighbors
      for (let i = 1; i < nodes.length; i++) {
        const n = nodes[i];
        ctx.beginPath();
        ctx.moveTo(center.x, center.y);
        ctx.lineTo(n.x, n.y);
        ctx.strokeStyle = hoveredIdx === i ? "rgba(230,237,243,0.18)" : "rgba(230,237,243,0.08)";
        ctx.lineWidth = hoveredIdx === i ? 1 : 0.5;
        ctx.stroke();
      }

      // Draw nodes + labels
      for (let i = nodes.length - 1; i >= 0; i--) {
        const n = nodes[i];
        const isHovered = hoveredIdx === i;
        const drawSize = isHovered ? n.size * 1.5 : n.size;

        // Glow on hover
        if (isHovered) {
          ctx.beginPath();
          ctx.arc(n.x, n.y, drawSize + 4, 0, Math.PI * 2);
          ctx.fillStyle = `${n.color}30`;
          ctx.fill();
        }

        // Node circle
        ctx.beginPath();
        ctx.arc(n.x, n.y, drawSize, 0, Math.PI * 2);
        ctx.fillStyle = n.color;
        ctx.fill();

        // Label
        if (n.isCenter || isHovered) {
          ctx.font = `${n.isCenter ? "500" : "400"} ${n.isCenter ? 9 : 8}px "SF Pro Display", -apple-system, sans-serif`;
          ctx.fillStyle = n.isCenter ? "rgba(230,237,243,0.8)" : "rgba(230,237,243,0.55)";
          ctx.textAlign = "center";
          ctx.fillText(
            n.title.length > 20 ? n.title.slice(0, 18) + "..." : n.title,
            n.x,
            n.y + drawSize + 11,
          );
        }
      }
    };

    draw();
    const observer = new ResizeObserver(() => draw());
    observer.observe(canvas);
    return () => observer.disconnect();
  }, [aliases, neighbors, currentCategories, hoveredIdx, dpr, currentTitle]);

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    let found = -1;
    for (let i = 1; i < layoutRef.current.length; i++) {
      const n = layoutRef.current[i];
      const dist = Math.sqrt((x - n.x) ** 2 + (y - n.y) ** 2);
      if (dist < 16) { found = i; break; }
    }
    setHoveredIdx(found >= 0 ? found : null);
    canvas.style.cursor = found >= 0 ? "pointer" : "default";
  }, []);

  const handleClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    for (let i = 1; i < layoutRef.current.length; i++) {
      const n = layoutRef.current[i];
      if (Math.sqrt((x - n.x) ** 2 + (y - n.y) ** 2) < 16) {
        onClickNode(n.slug);
        return;
      }
    }
  }, [onClickNode]);

  if (neighbors.length === 0) return null;

  return (
    <div className="mt-6">
      <p className="mb-2 text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
        Connections
      </p>
      <div className="overflow-hidden rounded-xl border border-[var(--border)]">
        <canvas
          ref={canvasRef}
          className="h-56 w-full"
          onMouseMove={handleMouseMove}
          onClick={handleClick}
          onMouseLeave={() => setHoveredIdx(null)}
        />
      </div>
      {neighbors.length > 14 && (
        <p className="mt-1.5 text-center text-[10px] text-[var(--muted-foreground)]">
          +{neighbors.length - 14} more connections
        </p>
      )}
    </div>
  );
}

/* ── Main Component ── */

interface WikiNoteProps {
  notePath: string;
  scrollRef: React.RefObject<HTMLDivElement | null>;
  onNavigate: (slug: string) => void;
  onHome: () => void;
  onOpenGraph: () => void;
  onOpenStats: () => void;
}

export function WikiNote({ notePath, scrollRef, onNavigate, onHome, onOpenGraph, onOpenStats }: WikiNoteProps) {
  const config = useWikiConfig();
  const [page, setPage] = useState<WikiPageData | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [revalidating, setRevalidating] = useState(false);
  const pageRehypePlugins = page?.hasCodeBlocks ? rehypePlugins : [];

  const load = useCallback(async (path: string) => {
    const slug = normalizeNotePath(path);
    if (!slug) {
      setError(new Response("Wiki page not found", { status: 404 }));
      return;
    }
    setRevalidating(true);
    try {
      const data = await fetchJson<WikiPageData>(`/api/wiki/${slug}`);
      setPage(data);
      setError(null);
    } catch (err) {
      setError(err);
    } finally {
      setRevalidating(false);
    }
  }, []);

  useEffect(() => {
    setPage(null);
    setError(null);
    void load(notePath);
    // Scroll the tab container back to top whenever the note changes
    scrollRef.current?.scrollTo(0, 0);
  }, [notePath, load, scrollRef]);

  const filteredHeadings = page?.headings.filter((h) => h.text !== "Source Notes") ?? [];
  const activeId = useActiveHeading(filteredHeadings, scrollRef);
  const portraitUrl = usePersonImage(page?.isPerson ? page.title : null);
  const [personOverrideError, setPersonOverrideError] = useState<string | null>(null);
  const [personOverrideBlocked, setPersonOverrideBlocked] = useState(false);
  const [isUpdatingPerson, setIsUpdatingPerson] = useState(false);

  if (error) {
    return <WikiErrorView status={statusOf(error)} message={messageOf(error)} onHome={onHome} />;
  }

  if (!page) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="animate-pulse text-sm text-[var(--muted-foreground)]">Loading note…</p>
      </div>
    );
  }

  const readTime = estimateReadingTime(page.contentMarkdown);
  const words = wordCount(page.contentMarkdown);
  const { mainContent, relatedLinks } = splitContentSections(page.contentMarkdown);
  const peopleControlsEnabled =
    config.people.mode !== "off" && !personOverrideBlocked;
  const personActionBusy = isUpdatingPerson || revalidating;
  const personPrimaryLabel =
    page.personOverride === "not-person" || (!page.isPerson && page.personOverride === null)
      ? "Mark as person"
      : "Mark as not person";
  const personPrimaryTarget =
    personPrimaryLabel === "Mark as person" ? "person" : "not-person";

  async function updatePersonOverride(nextOverride: "person" | "not-person" | null) {
    setIsUpdatingPerson(true);
    setPersonOverrideError(null);

    try {
      const response = await fetch(`/wapi/api/setup/person-override`, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          accept: "application/json",
        },
        body: JSON.stringify({
          file: page!.fileName,
          override: nextOverride,
        }),
      });

      // 409 = setup-surface endpoint unavailable in user mode → hide the control
      if (response.status === 409) {
        setPersonOverrideBlocked(true);
        setPersonOverrideError(null);
        return;
      }

      const payload = (await response.json().catch(() => null)) as { error?: string } | null;
      if (!response.ok) {
        throw new Error(payload?.error ?? "Could not update person override");
      }

      void load(notePath);
    } catch (err) {
      setPersonOverrideError(
        err instanceof Error ? err.message : "Could not update person override",
      );
    } finally {
      setIsUpdatingPerson(false);
    }
  }

  // Markdown-rendered wiki links are plain anchors; route them inside the
  // SPA instead of letting the browser do a full reload out of the tab.
  function handleArticleClick(e: React.MouseEvent) {
    const anchor = (e.target as HTMLElement).closest("a");
    if (!anchor) return;
    const href = anchor.getAttribute("href") ?? "";
    const slug = wikiSlugFromHref(href);
    if (slug) {
      e.preventDefault();
      onNavigate(slug);
    }
  }

  return (
    <div className="flex min-h-full flex-col">
      <header className="flex items-center justify-between gap-2 px-4 pb-3 pt-5 sm:gap-3 sm:px-6 sm:pb-4">
        <button
          type="button"
          onClick={onHome}
          className="font-display text-lg text-[var(--foreground)] sm:text-xl"
        >
          {config.siteTitle}
        </button>
        <div className="flex items-center gap-1.5 sm:gap-2.5">
          <button
            type="button"
            onClick={onOpenGraph}
            className="surface rounded-full px-3.5 py-2 text-sm font-medium text-[var(--foreground)] transition-[transform] duration-200 ease-[cubic-bezier(0.23,1,0.32,1)] active:scale-[0.96] sm:px-4"
          >
            {config.navigation.graphLabel}
          </button>
          <button
            type="button"
            onClick={onOpenStats}
            className="surface rounded-full px-3.5 py-2 text-sm font-medium text-[var(--foreground)] transition-[transform] duration-200 ease-[cubic-bezier(0.23,1,0.32,1)] active:scale-[0.96] sm:px-4"
          >
            {config.navigation.statsLabel}
          </button>
        </div>
      </header>

      <main className="animate-in mx-auto w-full max-w-3xl px-4 pt-4 sm:px-6 sm:pt-8 lg:px-8" style={{ paddingBottom: "4rem" }}>
        {/* Breadcrumb */}
        <nav className="mb-6 flex items-center gap-2 text-sm text-[var(--muted-foreground)]">
          <button
            type="button"
            onClick={onHome}
            className="transition-colors duration-150 hover:text-[var(--foreground)]"
          >
            Home
          </button>
          <span className="select-none">/</span>
          <span className="text-[var(--foreground)]">{page.title}</span>
        </nav>

        {/* Title + metadata */}
        <div className="mb-6 flex items-start gap-4 sm:mb-10 sm:gap-5">
          {page.isPerson && portraitUrl && (
            <img
              src={portraitUrl}
              alt={page.title}
              loading="eager"
              decoding="async"
              className="h-16 w-16 shrink-0 rounded-2xl object-cover shadow-[0_8px_24px_-12px_rgba(0,0,0,0.6)] sm:h-24 sm:w-24"
            />
          )}
          <div className="min-w-0">
            <h1
              className="font-display text-[2rem] font-light leading-[1.05] tracking-tight text-[var(--foreground)] sm:text-5xl"
            >
              {page.title}
            </h1>
            <div className="mt-3 flex flex-wrap items-center gap-1.5 text-xs text-[var(--muted-foreground)]/60">
              <span>{readTime} min read</span>
              <span className="select-none">·</span>
              <span>{words.toLocaleString()} words</span>
              {page.modifiedAt > 0 && (
                <>
                  <span className="select-none">·</span>
                  <span>Updated {formatDate(page.modifiedAt)}</span>
                </>
              )}
              {peopleControlsEnabled && (
                <>
                  <span className="select-none">·</span>
                  <button
                    type="button"
                    onClick={() => void updatePersonOverride(personPrimaryTarget)}
                    disabled={personActionBusy}
                    className="underline decoration-[var(--muted-foreground)]/30 underline-offset-2 transition-colors duration-150 hover:text-[var(--foreground)] disabled:cursor-wait disabled:opacity-70"
                  >
                    {personActionBusy ? "Saving..." : personPrimaryLabel}
                  </button>
                  {page.personOverride !== null && (
                    <>
                      <span className="select-none">·</span>
                      <button
                        type="button"
                        onClick={() => void updatePersonOverride(null)}
                        disabled={personActionBusy}
                        className="underline decoration-[var(--muted-foreground)]/30 underline-offset-2 transition-colors duration-150 hover:text-[var(--foreground)] disabled:cursor-wait disabled:opacity-70"
                      >
                        Clear override
                      </button>
                    </>
                  )}
                  {personOverrideError && (
                    <span className="text-red-400">{personOverrideError}</span>
                  )}
                </>
              )}
            </div>
          </div>
        </div>

        {/* Mobile TOC */}
        {filteredHeadings.length > 0 && (
          <div className="mb-6 lg:hidden rounded-lg border border-[var(--border)] bg-[var(--card)] px-4 py-3">
            <p className="mb-2 text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
              On this page
            </p>
            <div className="flex flex-wrap gap-x-4 gap-y-1">
              {filteredHeadings.filter((h) => h.level <= 2).map((h) => (
                <a
                  key={h.id}
                  href={`#${h.id}`}
                  onClick={(e) => {
                    e.preventDefault();
                    document.getElementById(h.id)?.scrollIntoView({ behavior: "smooth" });
                  }}
                  className="text-sm text-[var(--muted-foreground)] transition-colors duration-150 hover:text-[var(--foreground)]"
                >
                  {h.text}
                </a>
              ))}
            </div>
          </div>
        )}

        {/* Article + TOC */}
        <div className="relative">
          <article className="prose-wiki leading-[1.8]" onClick={handleArticleClick}>
            <ReactMarkdown
              rehypePlugins={pageRehypePlugins}
              remarkPlugins={remarkPlugins}
              components={markdownComponents}
            >
              {mainContent}
            </ReactMarkdown>
          </article>

          {/* Related Concepts as chips */}
          {relatedLinks.length > 0 && (
            <section id="related-concepts" className="mt-10 scroll-mt-20">
              <h2 className="font-display mb-4 border-b border-[var(--border)] pb-2 text-xl font-light text-[var(--foreground)]">
                Related Concepts
              </h2>
              <div className="flex flex-wrap gap-2">
                {relatedLinks.map((link) => {
                  const slug = wikiSlugFromHref(link.href);
                  return slug ? (
                    <button
                      key={link.href}
                      type="button"
                      onClick={() => onNavigate(slug)}
                      className="rounded-full border border-[var(--border)] bg-[var(--card)] px-3.5 py-1.5 text-sm transition-[color,background-color,transform] duration-150 hover:bg-[var(--secondary)] active:scale-[0.97]"
                    >
                      <span className="font-display font-light text-[var(--foreground)]">
                        {link.label}
                      </span>
                    </button>
                  ) : (
                    <a
                      key={link.href}
                      href={link.href}
                      target="_blank"
                      rel="noreferrer"
                      className="rounded-full border border-[var(--border)] bg-[var(--card)] px-3.5 py-1.5 text-sm transition-[color,background-color,transform] duration-150 hover:bg-[var(--secondary)] active:scale-[0.97]"
                    >
                      <span className="font-display font-light text-[var(--foreground)]">
                        {link.label}
                      </span>
                    </a>
                  );
                })}
              </div>
            </section>
          )}

          {/* Desktop sidebar — TOC + mini graph */}
          <aside className="hidden xl:block absolute -right-60 top-0 w-52">
            <div className="sticky top-8">
              {filteredHeadings.length > 0 && (
                <TableOfContents headings={filteredHeadings} activeId={activeId} />
              )}
              {page.neighbors.length > 0 && (
                <NeighborhoodGraph
                  currentTitle={page.title}
                  currentCategories={page.categories}
                  neighbors={page.neighbors}
                  onClickNode={onNavigate}
                  aliases={config.categories.aliases}
                />
              )}
            </div>
          </aside>
        </div>
      </main>
    </div>
  );
}
