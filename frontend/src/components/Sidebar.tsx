import { Settings } from "lucide-react";
import type { Health, SessionInfo } from "../types";

function relativeTime(epoch: number): string {
  const diff = Date.now() / 1000 - epoch;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`;
  return new Date(epoch * 1000).toLocaleDateString();
}

interface Props {
  health: Health | null;
  sessions: SessionInfo[];
  activeId: string | null;
  streaming: boolean;
  settingsOpen: boolean;
  onNewChat: () => void;
  onSelect: (sessionId: string) => void;
  onOpenSettings: () => void;
}

export default function Sidebar({
  health,
  sessions,
  activeId,
  streaming,
  settingsOpen,
  onNewChat,
  onSelect,
  onOpenSettings,
}: Props) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-name">NM-Agent-CLI</span>
        <span className="brand-sub">web</span>
      </div>

      <button className="new-chat" onClick={onNewChat} disabled={streaming}>
        + New chat
      </button>

      <div className="section-label">Sessions</div>
      <div className="session-list">
        {sessions.length === 0 && <div className="session-empty">No sessions yet</div>}
        {sessions.map((s) => (
          <button
            key={s.session_id}
            className={`session-row${s.session_id === activeId ? " active" : ""}`}
            onClick={() => onSelect(s.session_id)}
            disabled={streaming}
            title={s.session_id}
          >
            <span className="session-turns">{s.turns}t</span>
            <span className="session-time">{relativeTime(s.created_at)}</span>
          </button>
        ))}
      </div>

      <div className="sidebar-footer">
        {health ? (
          <>
            <div className="footer-row">
              <span className="dot ok" /> {health.model}
              <button
                className={`gear${settingsOpen ? " active" : ""}`}
                aria-label="Settings — skills and MCP servers"
                title="Skills & MCP settings"
                onClick={onOpenSettings}
              >
                <Settings size={14} />
              </button>
            </div>
            <div className="footer-row dim">
              {health.skills} skills · {health.wiki_available ? "wiki on" : "wiki off"}
              {health.mcp_tools > 0 ? ` · ${health.mcp_tools} mcp` : ""}
            </div>
          </>
        ) : (
          <div className="footer-row dim">connecting…</div>
        )}
      </div>
    </aside>
  );
}
