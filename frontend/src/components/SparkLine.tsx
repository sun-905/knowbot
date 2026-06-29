interface Props {
  data: { date: string; value: number }[];
  width?: number;
  height?: number;
}

/** 轻量 SVG 折线图，无外部依赖 */
export default function SparkLine({ data, width = 520, height = 180 }: Props) {
  if (!data.length) {
    return (
      <div
        style={{
          height,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--color-steel-dim)",
          fontSize: 13,
        }}
      >
        暂无数据
      </div>
    );
  }

  const pad = { top: 20, right: 20, bottom: 30, left: 40 };
  const w = width - pad.left - pad.right;
  const h = height - pad.top - pad.bottom;
  const maxVal = Math.max(...data.map((d) => d.value), 1);

  const points = data.map((d, i) => {
    const x = pad.left + (i / Math.max(data.length - 1, 1)) * w;
    const y = pad.top + h - (d.value / maxVal) * h;
    return { x, y, ...d };
  });

  const linePath = points.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ");
  const areaPath = `${linePath} L ${points[points.length - 1].x} ${pad.top + h} L ${points[0].x} ${pad.top + h} Z`;

  // Y 轴刻度（0, 25%, 50%, 75%, max）
  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((r) => Math.round(maxVal * r));

  return (
    <svg width={width} height={height} style={{ display: "block" }}>
      {/* Y 轴参考线 + 标签 */}
      {yTicks.map((tick) => {
        const y = pad.top + h - (tick / maxVal) * h;
        return (
          <g key={tick}>
            <line
              x1={pad.left}
              y1={y}
              x2={width - pad.right}
              y2={y}
              stroke="rgba(0,229,255,0.08)"
              strokeDasharray="3 3"
            />
            <text
              x={pad.left - 6}
              y={y + 4}
              textAnchor="end"
              fill="var(--color-steel-dim)"
              fontSize={10}
              fontFamily="var(--font-mono)"
            >
              {tick}
            </text>
          </g>
        );
      })}

      {/* 面积填充 */}
      <path d={areaPath} fill="url(#grad)" opacity={0.6} />
      <defs>
        <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--color-cyan)" stopOpacity={0.25} />
          <stop offset="100%" stopColor="var(--color-cyan)" stopOpacity={0} />
        </linearGradient>
      </defs>

      {/* 折线 */}
      <path d={linePath} fill="none" stroke="var(--color-cyan)" strokeWidth={2} strokeLinejoin="round" />

      {/* 数据点 */}
      {points.map((p, i) => (
        <g key={i}>
          <circle cx={p.x} cy={p.y} r={3} fill="var(--color-void)" stroke="var(--color-cyan)" strokeWidth={1.5} />
          {/* 悬停标签 */}
          <title>{`${p.date}: ${p.value}`}</title>
        </g>
      ))}

      {/* X 轴日期标签（隔一个显示，避免重叠） */}
      {points.map((p, i) => {
        if (data.length > 7 && i % Math.ceil(data.length / 7) !== 0) return null;
        return (
          <text
            key={i}
            x={p.x}
            y={height - 6}
            textAnchor="middle"
            fill="var(--color-steel-dim)"
            fontSize={10}
            fontFamily="var(--font-mono)"
          >
            {p.date.slice(5)}
          </text>
        );
      })}
    </svg>
  );
}
