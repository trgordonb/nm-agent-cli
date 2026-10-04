// Ported from wiki-os src/components/homepage-content.tsx (MIT).
// Link → onNavigate callback; avatar accent text colors remapped to the dark
// chip palette from wikios.css; safe-area padding simplified.

import { useState, type ReactNode } from "react";

import { useWikiConfig } from "./wiki-config-context";
import { type HomepageData, type PageSummary } from "./wiki-shared";
import { type HomepageSectionKey } from "./wiki-config";
import { usePersonImage } from "./use-person-image";

const categoryAccents = [
  "chip-teal",
  "chip-peach",
  "chip-lavender",
];

const personAvatarAccents = [
  "bg-[var(--teal-soft)] text-[#a5d3e0]",
  "bg-[var(--peach-soft)] text-[#f4c4a5]",
  "bg-[var(--lavender-soft)] text-[#d8c6f0]",
];

function PersonCard({
  person,
  index,
  onNavigate,
}: {
  person: PageSummary;
  index: number;
  onNavigate: (slug: string) => void;
}) {
  const imageUrl = usePersonImage(person.title);
  const accentBg = personAvatarAccents[index % personAvatarAccents.length];
  const [imgLoaded, setImgLoaded] = useState(false);

  return (
    <button
      type="button"
      onClick={() => onNavigate(person.slug)}
      className="surface hover-lift flex flex-col items-center gap-3 rounded-2xl px-4 py-4 text-center"
    >
      <span
        className={`relative flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-full ${accentBg} font-display text-2xl font-medium`}
      >
        {/* Fallback initial is always painted; image overlays once it loads */}
        <span aria-hidden={imageUrl !== null && imgLoaded}>{person.title.charAt(0)}</span>
        {imageUrl && (
          <img
            src={imageUrl}
            alt=""
            loading="lazy"
            decoding="async"
            onLoad={() => setImgLoaded(true)}
            className={`absolute inset-0 h-full w-full object-cover transition-opacity duration-300 ${
              imgLoaded ? "opacity-100" : "opacity-0"
            }`}
          />
        )}
      </span>
      <div className="min-w-0">
        <p className="truncate font-display text-[0.95rem] text-[var(--foreground)]">
          {person.title}
        </p>
        <p className="text-[0.7rem] font-medium text-[var(--muted-foreground)]">
          {person.backlinkCount} connections
        </p>
      </div>
    </button>
  );
}

function PageChip({
  page,
  index,
  onNavigate,
}: {
  page: PageSummary;
  index: number;
  onNavigate: (slug: string) => void;
}) {
  const accent = categoryAccents[index % categoryAccents.length];
  return (
    <button
      type="button"
      onClick={() => onNavigate(page.slug)}
      className={`${accent} group inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-sm transition-[transform,box-shadow] duration-200 ease-[cubic-bezier(0.23,1,0.32,1)] hover:-translate-y-0.5 hover:shadow-[0_8px_20px_-10px_rgba(0,0,0,0.5)] active:scale-[0.97]`}
    >
      <span className="font-display text-[0.95rem]">{page.title}</span>
      <span className="rounded-full bg-white/10 px-1.5 py-0.5 text-[0.65rem] font-semibold tabular-nums">
        {page.backlinkCount}
      </span>
    </button>
  );
}

export function HomepageContent({
  homepage,
  onNavigate,
}: {
  homepage: HomepageData;
  onNavigate: (slug: string) => void;
}) {
  const config = useWikiConfig();
  const labels = config.homepage.labels;
  const orderedSections = config.homepage.sectionOrder.filter((section): section is HomepageSectionKey => {
    return section !== "people" || homepage.people.length > 0;
  });
  const midpoint = Math.ceil(orderedSections.length / 2);
  const columns = [orderedSections.slice(0, midpoint), orderedSections.slice(midpoint)];

  const sectionViews: Record<HomepageSectionKey, ReactNode> = {
    featured: homepage.featured.length > 0 ? (
      <div>
        <div className="mb-4 flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-[var(--peach)] shadow-[0_0_12px_var(--peach)]" />
          <p className="text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-[var(--muted-foreground)]">
            {labels.featured}
          </p>
        </div>
        <div className="grid grid-cols-2 gap-2.5">
          {homepage.featured.map((page, index) => {
            const accentRail = [
              "before:bg-[var(--teal)]",
              "before:bg-[var(--peach)]",
              "before:bg-[var(--lavender)]",
            ][index % 3];
            return (
              <button
                key={page.file}
                type="button"
                onClick={() => onNavigate(page.slug)}
                className={`surface hover-lift relative overflow-hidden rounded-2xl px-4 py-3.5 text-left before:absolute before:left-0 before:top-0 before:h-full before:w-1 ${accentRail}`}
              >
                <p className="truncate pl-1 font-display text-[0.95rem] text-[var(--foreground)]">
                  {page.title}
                </p>
                <p className="mt-1 line-clamp-2 pl-1 text-[0.78rem] leading-relaxed text-[var(--muted-foreground)]">
                  {page.summary}
                </p>
                <div className="mt-2 flex items-center gap-2 pl-1 text-[0.65rem] font-medium text-[var(--muted-foreground)]">
                  <span>{page.wordCount.toLocaleString()} words</span>
                  <span>·</span>
                  <span>{page.backlinkCount} backlinks</span>
                </div>
              </button>
            );
          })}
        </div>
      </div>
    ) : null,
    topConnected: (
      <div>
        <div className="mb-4 flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-[var(--teal)] shadow-[0_0_12px_var(--teal)]" />
          <p className="text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-[var(--muted-foreground)]">
            {labels.topConnected}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {homepage.topConnected.map((page, index) => (
            <PageChip key={page.file} page={page} index={index} onNavigate={onNavigate} />
          ))}
        </div>
      </div>
    ),
    people: homepage.people.length > 0 ? (
      <div>
        <div className="mb-4 flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-[var(--lavender)] shadow-[0_0_12px_var(--lavender)]" />
          <p className="text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-[var(--muted-foreground)]">
            {labels.people}
          </p>
        </div>
        <div className="grid grid-cols-2 gap-2.5">
          {homepage.people.map((person, index) => (
            <PersonCard key={person.file} person={person} index={index} onNavigate={onNavigate} />
          ))}
        </div>
      </div>
    ) : null,
    recentPages: (
      <div>
        <div className="mb-4 flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-[var(--peach)] shadow-[0_0_12px_var(--peach)]" />
          <p className="text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-[var(--muted-foreground)]">
            {labels.recentPages}
          </p>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {homepage.recentPages.map((page, index) => {
            const accentRail = [
              "before:bg-[var(--teal)]",
              "before:bg-[var(--peach)]",
              "before:bg-[var(--lavender)]",
            ][index % 3];
            return (
              <button
                key={page.file}
                type="button"
                onClick={() => onNavigate(page.slug)}
                className={`animate-in hover-lift surface relative overflow-hidden rounded-2xl px-5 py-4 text-left before:absolute before:left-0 before:top-0 before:h-full before:w-1 ${accentRail} stagger-${Math.min(index + 1, 8)}`}
              >
                <p className="truncate pl-1 font-display text-[1.05rem] text-[var(--foreground)]">
                  {page.title}
                </p>
                <p className="mt-1 line-clamp-1 pl-1 text-[0.78rem] text-[var(--muted-foreground)]">
                  {page.summary}
                </p>
              </button>
            );
          })}
        </div>
      </div>
    ),
  };

  return (
    <div className="w-full space-y-10 pt-4 sm:space-y-12 sm:pt-6" style={{ paddingBottom: "4rem" }}>
      <div className="grid grid-cols-1 gap-8 sm:gap-10 lg:grid-cols-2">
        {columns.map((column, index) => (
          <section key={index} className="space-y-8 sm:space-y-10">
            {column.map((section) => sectionViews[section])}
          </section>
        ))}
      </div>
    </div>
  );
}
