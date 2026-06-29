import { Tag } from "antd";

interface Props {
  intent: string;
  source: string;
  confidence: number;
}

const SOURCE_STYLE: Record<string, { color: string; border: string }> = {
  rule: { color: "var(--color-success)", border: "rgba(105, 240, 174, 0.2)" },
  vector: { color: "var(--color-cyan)", border: "rgba(0, 229, 255, 0.2)" },
  llm: { color: "var(--color-amber)", border: "rgba(255, 183, 77, 0.2)" },
};

const SOURCE_LABEL: Record<string, string> = {
  rule: "规则",
  vector: "向量",
  llm: "大模型",
};

const INTENT_LABEL: Record<string, string> = {
  "投诉": "投诉",
  "售后问题": "售后",
  "产品咨询": "咨询",
  "订单查询": "订单",
  "账号问题": "账号",
  "闲聊": "闲聊",
};

export default function IntentBadge({ intent, source, confidence }: Props) {
  if (!intent) return null;

  const style = SOURCE_STYLE[source] || { color: "var(--color-steel-dim)", border: "rgba(255,255,255,0.06)" };

  return (
    <Tag
      style={{
        fontSize: 11,
        fontFamily: "var(--font-mono)",
        color: style.color,
        border: `1px solid ${style.border}`,
        borderRadius: 2,
        background: "transparent",
        letterSpacing: "0.02em",
      }}
    >
      {INTENT_LABEL[intent] || intent}
      <span style={{ marginLeft: 4, opacity: 0.6 }}>{SOURCE_LABEL[source] || source}</span>
      <span style={{ marginLeft: 2, opacity: 0.5 }}>{(confidence * 100).toFixed(0)}%</span>
    </Tag>
  );
}
