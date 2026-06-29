import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Props {
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
}

export default function ChatBubble({ role, content, isStreaming }: Props) {
  const isUser = role === "user";

  return (
    <div
      style={{
        display: "flex",
        justifyContent: isUser ? "flex-end" : "flex-start",
        marginBottom: 16,
        animation: "fade-in-up 0.2s ease",
        position: "relative",
        zIndex: 1,
      }}
    >
      <div
        style={{
          maxWidth: "75%",
          padding: "14px 18px",
          borderRadius: isUser ? "4px 4px 0 4px" : "4px 4px 4px 0",
          background: isUser
            ? "linear-gradient(135deg, rgba(0, 229, 255, 0.15), rgba(0, 229, 255, 0.06))"
            : "rgba(17, 22, 51, 0.9)",
          border: isUser
            ? "1px solid rgba(0, 229, 255, 0.2)"
            : "1px solid rgba(255, 255, 255, 0.06)",
          color: isUser ? "var(--color-steel)" : "var(--color-steel)",
          lineHeight: 1.7,
          fontSize: 14,
          // Subtle glow on user messages
          boxShadow: isUser
            ? "0 0 12px rgba(0, 229, 255, 0.08)"
            : "0 1px 8px rgba(0, 0, 0, 0.2)",
        }}
      >
        {isUser ? (
          <span style={{ whiteSpace: "pre-wrap" }}>{content}</span>
        ) : (
          <div>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
            {isStreaming && (
              <span className="cursor-blink" style={{ color: "var(--color-cyan)" }}>
                ▊
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
