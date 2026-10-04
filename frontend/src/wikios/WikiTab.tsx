// Wiki tab controller: holds the note/graph/stats sub-view state (upstream:
// react-router routes), bootstraps /api/config like upstream main.tsx, and
// provides the .wikios-scoped container the scoped CSS + graph stage need.

import { useEffect, useRef, useState } from "react";

import "./wikios.css";

import {
  DEFAULT_WIKI_OS_CONFIG,
  WikiConfigProvider,
  applyThemeVariables,
} from "./wiki-config-context";
import type { WikiOsConfig } from "./wiki-config";
import { fetchJson } from "./api";
import { WikiNote } from "./WikiNote";
import { WikiGraph } from "./WikiGraph";
import { WikiStatsView } from "./WikiStatsView";
import { WikiSearch } from "./WikiSearch";

type WikiView =
  | { kind: "home" }
  | { kind: "note"; path: string }
  | { kind: "graph" }
  | { kind: "stats" };

export function WikiTab() {
  const [config, setConfig] = useState<WikiOsConfig | null>(null);
  const [view, setView] = useState<WikiView>({ kind: "home" });
  const scrollRef = useRef<HTMLDivElement>(null);

  // Same bootstrap contract as upstream main.tsx: config fetch may fail →
  // render with defaults.
  useEffect(() => {
    let alive = true;
    fetchJson<WikiOsConfig>("/api/config")
      .then((c) => {
        if (alive) setConfig(c);
      })
      .catch(() => {
        if (alive) setConfig(DEFAULT_WIKI_OS_CONFIG);
      });
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (config) applyThemeVariables(config);
  }, [config]);

  // The note view scrolls the tab container; graph is an overlay (no scroll)
  useEffect(() => {
    if (view.kind !== "note") return;
    scrollRef.current?.scrollTo(0, 0);
  }, [view]);

  return (
    <div className="wikios wiki-tab">
      <WikiConfigProvider config={config ?? DEFAULT_WIKI_OS_CONFIG}>
        {view.kind === "graph" ? (
          <WikiGraph
            onNavigate={(slug) => setView({ kind: "note", path: slug })}
            onHome={() => setView({ kind: "home" })}
            onOpenStats={() => setView({ kind: "stats" })}
          />
        ) : (
          <div ref={scrollRef} className="wiki-tab-scroll">
            {view.kind === "home" && (
              <WikiSearch
                onNavigate={(slug) => setView({ kind: "note", path: slug })}
                onOpenGraph={() => setView({ kind: "graph" })}
                onOpenStats={() => setView({ kind: "stats" })}
              />
            )}
            {view.kind === "note" && (
              <WikiNote
                key={view.path}
                notePath={view.path}
                scrollRef={scrollRef}
                onNavigate={(slug) => setView({ kind: "note", path: slug })}
                onHome={() => setView({ kind: "home" })}
                onOpenGraph={() => setView({ kind: "graph" })}
                onOpenStats={() => setView({ kind: "stats" })}
              />
            )}
            {view.kind === "stats" && (
              <WikiStatsView
                onHome={() => setView({ kind: "home" })}
                onOpenGraph={() => setView({ kind: "graph" })}
              />
            )}
          </div>
        )}
      </WikiConfigProvider>
    </div>
  );
}
