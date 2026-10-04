import { useEffect, useRef } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { FeedItem, MessageItem, ToolCall } from "../types";

function shortArgs(args: Record<string, unknown>): string {
  const raw = JSON.stringify(args);
  return raw.length > 80 ? `${raw.slice(0, 80)}…` : raw;
}

function ToolRow({ call }: { call: ToolCall }) {
  return (
    <div className="tool-call">
      tools › {call.name}({shortArgs(call.args)})
    </div>
  );
}

function MessageRow({ item }: { item: MessageItem }) {
  if (item.role === "user") {
    return (
      <div className="msg user">
        <div className="role-label">you »</div>
        <div className="user-content">{item.content}</div>
      </div>
    );
  }

  if (item.role === "tool") {
    const failed = item.content.startsWith("Rejected:") || item.content.startsWith("Error:");
    return (
      <details className={`tool-result${failed ? " failed" : ""}`}>
        <summary>
          {failed ? "✗" : "✓"} {item.toolName ?? "tool"}
          {item.status ? ` · ${item.status}` : ""}
        </summary>
        <pre>{item.content}</pre>
      </details>
    );
  }

  return (
    <div className="msg assistant">
      <div className="role-label">agent</div>
      {item.toolCalls?.map((call) => <ToolRow key={call.id} call={call} />)}
      {item.content && (
        <div className="md">
          <Markdown remarkPlugins={[remarkGfm]}>{item.content}</Markdown>
        </div>
      )}
    </div>
  );
}

export default function Feed({ items }: { items: FeedItem[] }) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const stickRef = useRef(true);

  useEffect(() => {
    const el = scrollRef.current;
    if (el && stickRef.current) {
      el.scrollTop = el.scrollHeight;
    }
  }, [items]);

  return (
    <div
      className="feed-scroll"
      ref={scrollRef}
      onScroll={(e) => {
        const el = e.currentTarget;
        stickRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
      }}
    >
      {items.map((item) => {
        if (item.kind === "system") {
          return (
            <div key={item.id} className={`system-row ${item.tone}`}>
              {item.text}
            </div>
          );
        }
        if (item.kind === "notice") {
          return (
            <div key={item.id} className={`notice ${item.tone}`}>
              {item.text}
            </div>
          );
        }
        return <MessageRow key={item.id} item={item} />;
      })}
    </div>
  );
}
