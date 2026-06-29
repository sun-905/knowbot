interface Props {
  references: { doc_name: string; doc_id: number; score: number; snippet?: string }[];
}

/** 去掉文件扩展名 */
function bareName(name: string): string {
  return name.replace(/\.(pdf|txt|md)$/i, "");
}

export default function ReferenceCard({ references }: Props) {
  if (!references.length) return null;

  return (
    <div
      style={{
        marginTop: 10,
        position: "relative",
        zIndex: 1,
        animation: "fade-in 0.3s ease",
      }}
    >
      <div
        style={{
          fontSize: 11,
          color: "var(--color-cyan)",
          fontWeight: 600,
          fontFamily: "var(--font-display)",
          letterSpacing: "0.06em",
          marginBottom: 8,
        }}
      >
        ◆ 参考来源
      </div>
      {references.map((r, i) => (
        <div
          key={i}
          style={{
            padding: "8px 12px",
            marginBottom: 6,
            background: "rgba(0, 229, 255, 0.03)",
            border: "1px solid rgba(0, 229, 255, 0.08)",
            borderLeft: "2px solid var(--color-cyan)",
            borderRadius: "0 4px 4px 0",
            fontSize: 12,
            lineHeight: 1.6,
          }}
        >
          <div
            style={{
              color: "var(--color-steel)",
              fontWeight: 600,
              marginBottom: 2,
            }}
          >
            《{bareName(r.doc_name)}》
          </div>
          {r.snippet && (
            <div style={{ color: "var(--color-steel-dim)" }}>
              {r.snippet}
              {r.snippet.length >= 100 ? "…" : ""}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
