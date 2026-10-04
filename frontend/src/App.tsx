import { useCallback, useEffect, useRef, useState } from "react";
import { cancelTurn, getHealth, getSessionMessages, getSessions, streamChat } from "./api";
import type { FeedItem, NewItem, Health, SessionInfo, ToolCall } from "./types";
import Sidebar from "./components/Sidebar";
import Feed from "./components/Feed";
import Composer from "./components/Composer";
import SkillsTab from "./components/SkillsTab";
import McpTab from "./components/McpTab";
import { WikiTab } from "./wikios/WikiTab";

let idCounter = 0;
const nextId = () => `item-${++idCounter}`;

type View = "chat" | "wiki" | "settings";
type SettingsSection = "skills" | "mcp";

export default function App() {
  const [view, setView] = useState<View>("chat");
  const [settingsSection, setSettingsSection] = useState<SettingsSection>("skills");
  const [health, setHealth] = useState<Health | null>(null);
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [items, setItems] = useState<FeedItem[]>([]);
  const [streaming, setStreaming] = useState(false);
  const turnIdRef = useRef<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const refreshSessions = useCallback(() => {
    getSessions()
      .then(setSessions)
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => undefined);
    refreshSessions();
  }, [refreshSessions]);

  const push = useCallback((item: NewItem) => {
    setItems((prev) => [...prev, { id: nextId(), ...item } as FeedItem]);
  }, []);

  const handleEvent = useCallback(
    (event: string, data: Record<string, unknown>) => {
      switch (event) {
        case "session": {
          turnIdRef.current = String(data.turn_id);
          setSessionId(String(data.session_id));
          break;
        }
        case "wiki":
          push({
            kind: "system",
            text: `wiki ∙ ${data.pages} matching page(s) recalled`,
            tone: "info",
          });
          break;
        case "compression":
          push({
            kind: "system",
            text: `context compression — turns ${data.first}-${data.last} summarized by ${data.model} (${data.original} → ${data.compressed} messages)`,
            tone: "info",
          });
          break;
        case "message": {
          const role = (data.role as string | undefined) ?? "assistant";
          push({
            kind: "message",
            role: role === "user" || role === "assistant" || role === "tool" ? role : "assistant",
            content: String(data.content ?? ""),
            toolCalls: Array.isArray(data.tool_calls) ? (data.tool_calls as ToolCall[]) : undefined,
            toolCallId: data.tool_call_id as string | undefined,
            toolName: data.tool_name as string | undefined,
            status: data.status as string | undefined,
          });
          break;
        }
        case "nudge":
          push({ kind: "system", text: `memory nudge — ${data.summary}`, tone: "info" });
          break;
        case "cancelled":
          push({ kind: "system", text: "turn cancelled — partial state saved", tone: "warn" });
          break;
        case "error":
          push({ kind: "notice", text: `error: ${data.error}`, tone: "warn" });
          setStreaming(false);
          break;
        case "done":
          setStreaming(false);
          refreshSessions();
          break;
      }
    },
    [push, refreshSessions],
  );

  const send = useCallback(
    async (text: string) => {
      if (streaming || !text.trim()) return;
      setStreaming(true);
      push({ kind: "message", role: "user", content: text });
      const controller = new AbortController();
      abortRef.current = controller;
      try {
        await streamChat(text, sessionId, controller.signal, handleEvent);
      } catch (err) {
        const aborted = err instanceof DOMException && err.name === "AbortError";
        if (!aborted) {
          push({
            kind: "notice",
            text: `error: ${err instanceof Error ? err.message : String(err)}`,
            tone: "warn",
          });
        }
      } finally {
        abortRef.current = null;
        setStreaming(false);
        refreshSessions();
      }
    },
    [streaming, sessionId, handleEvent, push, refreshSessions],
  );

  const stop = useCallback(() => {
    if (turnIdRef.current) {
      cancelTurn(turnIdRef.current).catch(() => undefined);
    }
  }, []);

  const loadSession = useCallback(
    async (sid: string) => {
      if (streaming) return;
      try {
        const { messages } = await getSessionMessages(sid);
        setSessionId(sid);
        setItems(
          messages.map((m) => ({
            kind: "message" as const,
            id: nextId(),
            role: m.role,
            content: m.content,
            toolCalls: m.tool_calls,
            toolCallId: m.tool_call_id,
            toolName: m.tool_name,
            status: m.status,
          })),
        );
      } catch (err) {
        push({
          kind: "notice",
          text: `error: ${err instanceof Error ? err.message : String(err)}`,
          tone: "warn",
        });
      }
    },
    [streaming, push],
  );

  const newChat = useCallback(() => {
    if (streaming) return;
    setSessionId(null);
    setItems([]);
  }, [streaming]);

  return (
    <div className="app">
      {view !== "wiki" && (
        <Sidebar
          health={health}
          sessions={sessions}
          activeId={sessionId}
          streaming={streaming}
          settingsOpen={view === "settings"}
          onNewChat={newChat}
          onSelect={loadSession}
          onOpenSettings={() => setView("settings")}
        />
      )}
      <div className="content">
        <div className="tabbar" role="tablist">
          <button
            className={`tab${view === "chat" ? " active" : ""}`}
            role="tab"
            aria-selected={view === "chat"}
            onClick={() => setView("chat")}
          >
            Chat
          </button>
          <button
            className={`tab${view === "wiki" ? " active" : ""}`}
            role="tab"
            aria-selected={view === "wiki"}
            onClick={() => setView("wiki")}
          >
            Wiki
          </button>
        </div>
        {view === "chat" ? (
          <main className="main">
            <div className="feed" aria-live="polite">
              {items.length === 0 && (
                <div className="empty">
                  <div className="empty-title">NM-Agent-CLI</div>
                  <div className="empty-sub">
                    Ask anything — EDGAR, market data, web research, the wiki. The agent
                    streams tool calls and answers here; anything risky stays on your machine.
                  </div>
                </div>
              )}
              <Feed items={items} />
            </div>
            <Composer streaming={streaming} onSend={send} onStop={stop} />
          </main>
        ) : view === "wiki" ? (
          <WikiTab />
        ) : (
          <div className="settings">
            <div className="tabbar" role="tablist" aria-label="Settings sections">
              <button
                className={`tab${settingsSection === "skills" ? " active" : ""}`}
                role="tab"
                aria-selected={settingsSection === "skills"}
                onClick={() => setSettingsSection("skills")}
              >
                Skills
              </button>
              <button
                className={`tab${settingsSection === "mcp" ? " active" : ""}`}
                role="tab"
                aria-selected={settingsSection === "mcp"}
                onClick={() => setSettingsSection("mcp")}
              >
                MCP
              </button>
            </div>
            {settingsSection === "skills" ? <SkillsTab /> : <McpTab />}
          </div>
        )}
      </div>
    </div>
  );
}
