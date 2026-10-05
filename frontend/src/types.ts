export type Role = "user" | "assistant" | "tool";

export interface ToolCall {
  id: string;
  name: string;
  args: Record<string, unknown>;
}

/** One rendered row in the conversation feed. */
export type FeedItem =
  | MessageItem
  | SystemItem
  | NoticeItem;

export interface MessageItem {
  kind: "message";
  id: string;
  role: Role;
  content: string;
  toolCalls?: ToolCall[];
  toolCallId?: string;
  toolName?: string;
  status?: string;
}

/** Dim inline status rows: wiki recall, compression, nudges, cancel notices. */
export interface SystemItem {
  kind: "system";
  id: string;
  text: string;
  tone: "info" | "warn";
}

/** Persistent banner across the top of the feed (session resumed / errors). */
export interface NoticeItem {
  kind: "notice";
  id: string;
  text: string;
  tone: "info" | "warn";
}

/** Omit that distributes over unions — id-less FeedItem for queueing new rows. */
export type NewItem = DistributiveOmit<FeedItem, "id">;
type DistributiveOmit<T, K extends PropertyKey> = T extends unknown ? Omit<T, K> : never;

export interface SessionInfo {
  session_id: string;
  created_at: number;
  turns: number;
  /** One-line title (fallback: truncated first user message); null until first turn. */
  summary?: string | null;
}

export interface Health {
  status: string;
  model: string;
  memory_chars: number;
  skills: number;
  wiki_available: boolean;
  mcp_tools: number;
  assembled: boolean;
}

/** Admin view of a registry skill (GET /api/skills — includes disabled ones). */
export interface SkillInfo {
  name: string;
  description: string;
  path: string;
  rel_dir: string;
  enabled: boolean;
}

/** One MCP server from mcp_servers.json (GET /api/mcp). */
export interface McpServerInfo {
  name: string;
  enabled: boolean;
  description: string;
  transport: string;
  error: string | null;
  connected: boolean | null;
  tool_count: number | null;
  connect_error: string | null;
}

export interface McpListResponse {
  assembled: boolean;
  servers: McpServerInfo[];
}

export interface ApiMessage {
  type: string;
  role: Role;
  content: string;
  tool_calls?: ToolCall[];
  tool_call_id?: string;
  tool_name?: string;
  status?: string;
}
