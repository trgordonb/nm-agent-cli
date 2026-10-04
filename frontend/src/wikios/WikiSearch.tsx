// Ported from wiki-os src/components/search-box.tsx (MIT) — the wiki tab's
// start view. The homepage sections it used to host below the search box are
// skipped (no home-route in this integration); Links → callbacks; the page
// count is fetched here instead of via the home loader.

import {
  startTransition,
  useCallback,
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { ArrowUp, RefreshCw, Search } from "lucide-react";

import { useWikiConfig } from "./wiki-config-context";
import { HighlightedText, buildHighlightQuery } from "./highlighted-text";
import { slugFromFileName, titleFromFileName, type HomepageData, type SearchResult } from "./wiki-shared";
import { fetchJson } from "./api";
import { HomepageContent } from "./HomepageContent";

function SearchInput({
  query,
  onChange,
  onSubmit,
  inputRef,
}: {
  query: string;
  onChange: (value: string) => void;
  onSubmit: (event: React.FormEvent) => void;
  inputRef: React.RefObject<HTMLInputElement | null>;
}) {
  const config = useWikiConfig();

  return (
    <form onSubmit={onSubmit} className="group relative w-full">
      <div
        aria-hidden
        className="absolute -inset-[1px] rounded-full bg-gradient-to-r from-[var(--teal)] via-[var(--lavender)] to-[var(--peach)] opacity-0 blur-sm transition-opacity duration-300 group-focus-within:opacity-70"
      />
      <div className="surface-raised relative flex items-center rounded-full">
        <Search className="pointer-events-none absolute left-5 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted-foreground)] transition-colors duration-200 group-focus-within:text-[var(--teal)]" />
        <input
          ref={inputRef}
          type="search"
          value={query}
          onChange={(event) => onChange(event.target.value)}
          placeholder={config.searchPlaceholder}
          className="w-full rounded-full bg-transparent py-3.5 pl-12 pr-14 text-[0.95rem] text-[var(--foreground)] outline-none placeholder:text-[var(--muted-foreground)]"
        />
        <button
          type="submit"
          className="absolute right-2 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-full bg-[var(--foreground)] text-[var(--background)] shadow-[0_4px_12px_-4px_rgba(0,0,0,0.5)] transition-[transform,box-shadow,background] duration-200 ease-[cubic-bezier(0.23,1,0.32,1)] hover:bg-[var(--teal)] hover:shadow-[0_6px_16px_-4px_rgba(133,185,201,0.6)] active:scale-[0.92]"
        >
          <ArrowUp className="h-4 w-4" />
        </button>
      </div>
    </form>
  );
}

function splitBrandTitle(title: string) {
  // Split on camelCase / PascalCase boundary (e.g. "WikiOS" → "Wiki" + "OS")
  const camelMatch = title.match(/^(.+?)([A-Z][A-Z]+)$/);
  if (camelMatch) {
    return { lead: camelMatch[1], accent: camelMatch[2] };
  }

  const words = title.trim().split(/\s+/).filter(Boolean);

  if (words.length <= 1) {
    const midpoint = Math.max(1, Math.ceil(title.length / 2));
    return {
      lead: title.slice(0, midpoint),
      accent: title.slice(midpoint),
    };
  }

  return {
    lead: words.slice(0, -1).join(" "),
    accent: words[words.length - 1] ?? "",
  };
}

interface WikiSearchProps {
  onNavigate: (slug: string) => void;
  onOpenGraph: () => void;
  onOpenStats: () => void;
}

export function WikiSearch({ onNavigate, onOpenGraph, onOpenStats }: WikiSearchProps) {
  const config = useWikiConfig();
  const [homepage, setHomepage] = useState<HomepageData | null>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const deferredQuery = useDeferredValue(query);
  const highlight = useMemo(() => buildHighlightQuery(deferredQuery), [deferredQuery]);

  const loadHome = useCallback(() => {
    fetchJson<HomepageData>("/api/home")
      .then(setHomepage)
      .catch(() => setHomepage(null));
  }, []);

  useEffect(() => {
    loadHome();
  }, [loadHome]);

  useEffect(() => {
    const trimmedQuery = deferredQuery.trim();

    if (!trimmedQuery) {
      abortRef.current?.abort();
      return;
    }

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    const timer = setTimeout(async () => {
      try {
        const response = await fetchJson<{ error?: string; results?: SearchResult[] }>(
          `/api/search?q=${encodeURIComponent(trimmedQuery)}`,
          { signal: controller.signal },
        );

        if (!controller.signal.aborted) {
          startTransition(() => {
            setResults(response.results ?? []);
            setIsSearching(false);
            setSearchError(null);
          });
        }
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }

        if (!controller.signal.aborted) {
          setIsSearching(false);
          setSearchError(error instanceof Error ? error.message : "Search failed");
        }
      }
    }, 250);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [deferredQuery]);

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
  };

  const handleQueryChange = (value: string) => {
    const trimmedValue = value.trim();

    setQuery(value);
    setIsSearching(trimmedValue.length > 0);
    setSearchError(null);

    if (!trimmedValue) {
      setResults(null);
    }
  };

  const resetSearch = () => {
    setQuery("");
    setResults(null);
    setIsSearching(false);
    setSearchError(null);
    abortRef.current?.abort();
    inputRef.current?.focus();
  };

  const hasQuery = query.trim().length > 0;
  const showResults = hasQuery;
  const refreshBusy = isRefreshing;
  const brandTitle = splitBrandTitle(config.siteTitle);

  const refreshCount = async () => {
    if (refreshBusy) return;

    setIsRefreshing(true);

    try {
      // Force a fresh server snapshot when admin reindex is available.
      await fetchJson("/api/admin/reindex", { method: "POST" });
    } catch {
      // Reindex may be unavailable in user mode — just re-read the count.
    }
    loadHome();
    setIsRefreshing(false);
  };

  return (
    <div className="relative flex min-h-full flex-col">
      <header className="relative flex items-center justify-between gap-2 px-4 pb-3 pt-5 sm:gap-3 sm:px-6 sm:pb-4">
        <button
          type="button"
          onClick={resetSearch}
          className={`font-display text-lg text-[var(--foreground)] transition-opacity duration-200 sm:text-xl ${
            showResults ? "opacity-100" : "opacity-0 pointer-events-none"
          }`}
        >
          {config.siteTitle}
        </button>
        <div className="flex items-center gap-1.5 sm:gap-2.5">
          <button
            type="button"
            onClick={refreshCount}
            disabled={refreshBusy}
            title="Refresh wiki count"
            className="surface flex items-center gap-1.5 rounded-full px-3 py-2 text-xs text-[var(--muted-foreground)] transition-[transform] duration-200 ease-[cubic-bezier(0.23,1,0.32,1)] active:scale-[0.96] disabled:cursor-wait disabled:opacity-75 sm:gap-2 sm:px-3.5"
          >
            <RefreshCw
              className={`h-3.5 w-3.5 text-[var(--teal)] ${refreshBusy ? "animate-spin" : ""}`}
            />
            <span className="font-semibold tabular-nums text-[var(--foreground)]">
              {homepage === null ? "…" : homepage.totalPages.toLocaleString()}
            </span>
            <span className="hidden sm:inline">articles</span>
          </button>
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

      <main
        className={`relative flex flex-1 flex-col items-center px-4 ${
          showResults ? "pt-2 sm:pt-4" : "pt-8 sm:pt-20"
        }`}
      >
        <div
          className={`flex w-full max-w-4xl flex-col items-center gap-6 sm:gap-10 ${
            showResults ? "" : "animate-in"
          }`}
        >
          {!showResults && (
            <h1 className="font-display text-[clamp(3.25rem,14vw,8rem)] leading-[0.95] tracking-[-0.035em] text-[var(--foreground)]" style={{ fontWeight: 300 }}>
              {brandTitle.lead}
              <span className="bg-gradient-to-r from-[var(--teal)] via-[var(--lavender)] to-[var(--peach)] bg-clip-text text-transparent" style={{ fontWeight: 400 }}>
                {brandTitle.accent ?? ""}
              </span>
            </h1>
          )}

          <div className="w-full max-w-xl">
            <SearchInput
              query={query}
              onChange={handleQueryChange}
              onSubmit={handleSubmit}
              inputRef={inputRef}
            />

            {hasQuery && (
              <div className="animate-in surface-raised mt-3 overflow-hidden rounded-3xl">
                {isSearching ? (
                  <div className="space-y-3 p-4">
                    {[1, 2, 3].map((item) => (
                      <div
                        key={item}
                        className="animate-pulse space-y-2 rounded-xl bg-[var(--secondary)] p-4"
                      >
                        <div className="h-4 w-2/3 rounded bg-[var(--border)]" />
                        <div className="h-3 w-full rounded bg-[var(--border)]" />
                      </div>
                    ))}
                  </div>
                ) : results && results.length === 0 ? (
                  <div className="p-6 text-sm text-[var(--muted-foreground)]">
                    No matches for{" "}
                    <span className="font-semibold text-[var(--foreground)]">{query}</span>
                  </div>
                ) : searchError ? (
                  <div className="p-6 text-sm text-[var(--muted-foreground)]">
                    Search is temporarily unavailable. Please try again in a moment.
                  </div>
                ) : results ? (
                  <div className="divide-y divide-[var(--border)]">
                    {results.map((result, index) => {
                      const title = titleFromFileName(result.file);
                      const slug = slugFromFileName(result.file);
                      const staggerClass = `stagger-${Math.min(index + 1, 8)}`;
                      const accent = ["var(--teal)", "var(--peach)", "var(--lavender)"][index % 3];

                      return (
                        <button
                          key={result.file}
                          type="button"
                          onClick={() => onNavigate(slug)}
                          className={`animate-in group relative block w-full px-5 py-4 text-left transition-[background-color] duration-150 hover:bg-white/5 ${staggerClass}`}
                        >
                          <span
                            aria-hidden
                            className="absolute left-0 top-1/2 h-0 w-1 -translate-y-1/2 rounded-r-full transition-all duration-200 group-hover:h-[70%]"
                            style={{ background: accent }}
                          />
                          <p className="truncate font-display text-[1.05rem] text-[var(--foreground)]">
                            {title}
                          </p>
                          {result.matches.length > 0 && (
                            <p className="mt-2 line-clamp-2 text-[0.85rem] leading-relaxed text-[var(--muted-foreground)]">
                              <HighlightedText
                                highlight={highlight}
                                text={result.matches[0].snippet}
                              />
                            </p>
                          )}
                        </button>
                      );
                    })}
                  </div>
                ) : null}
              </div>
            )}
          </div>

          {!showResults && homepage && (
            <HomepageContent homepage={homepage} onNavigate={onNavigate} />
          )}
        </div>
      </main>
    </div>
  );
}
