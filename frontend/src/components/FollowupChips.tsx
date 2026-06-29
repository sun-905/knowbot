import { Tag } from "antd";

interface Props {
  items: string[];
  onSelect: (q: string) => void;
  disabled?: boolean;
}

export default function FollowupChips({ items, onSelect, disabled }: Props) {
  if (!items.length) return null;

  return (
    <div style={{ marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap", position: "relative", zIndex: 1 }}>
      <span style={{ fontSize: 12, color: "var(--color-steel-dim)", flexShrink: 0, lineHeight: "24px" }}>
        追问建议
      </span>
      {items.map((q, i) => (
        <Tag
          key={i}
          style={{
            cursor: disabled ? "not-allowed" : "pointer",
            opacity: disabled ? 0.4 : 1,
            border: "1px solid rgba(0, 229, 255, 0.2)",
            borderRadius: 2,
            transition: "all 0.15s ease",
          }}
          onClick={() => !disabled && onSelect(q)}
          onMouseEnter={(e) => {
            if (!disabled) {
              (e.currentTarget as HTMLElement).style.boxShadow = "0 0 8px rgba(0, 229, 255, 0.2)";
              (e.currentTarget as HTMLElement).style.borderColor = "rgba(0, 229, 255, 0.4)";
            }
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLElement).style.boxShadow = "";
            (e.currentTarget as HTMLElement).style.borderColor = "rgba(0, 229, 255, 0.2)";
          }}
        >
          {q}
        </Tag>
      ))}
    </div>
  );
}
