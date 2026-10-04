// Ported from wiki-os src/client/wiki-config.tsx (MIT). The provider is
// mounted by WikiTab, which also does the /api/config fetch that upstream
// main.tsx performed at bootstrap (same fallback to defaults on failure).

import { createContext, useContext, type ReactNode } from "react";

import {
  DEFAULT_WIKI_OS_CONFIG,
  type WikiOsConfig,
  getTopicColor,
  getTopicEmoji,
} from "./wiki-config";

const WikiConfigContext = createContext<WikiOsConfig>(DEFAULT_WIKI_OS_CONFIG);

export { DEFAULT_WIKI_OS_CONFIG };
export type { WikiOsConfig };

export function WikiConfigProvider({
  config,
  children,
}: {
  config: WikiOsConfig;
  children: ReactNode;
}) {
  return (
    <WikiConfigContext.Provider value={config}>
      {children}
    </WikiConfigContext.Provider>
  );
}

export function useWikiConfig() {
  return useContext(WikiConfigContext);
}

export function applyThemeVariables(config: WikiOsConfig) {
  if (typeof document === "undefined") {
    return;
  }

  const root = document.documentElement;
  for (const [name, value] of Object.entries(config.theme.variables)) {
    root.style.setProperty(name, value);
  }
}

export function getPrimaryTopicColor(categories: string[], config: WikiOsConfig) {
  for (const category of categories) {
    return getTopicColor(category, config.categories.aliases);
  }

  return "#9ca3af";
}

export function getPrimaryTopicEmoji(topic: string, config: WikiOsConfig) {
  return getTopicEmoji(topic, config.categories.aliases);
}
