import { useEffect, useRef } from "react";

interface Props {
  /** AI 思考时增亮粒子网络 */
  active: boolean;
}

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  r: number;
  opacity: number;
}

/**
 * RAG Pulse — 签名视觉元素。
 * 聊天背景中缓慢移动的粒子网络，
 * 代表知识图谱始终在"倾听"。
 * AI 流式输出时脉冲变亮。
 */
export default function RagPulse({ active }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const particlesRef = useRef<Particle[]>([]);
  const animRef = useRef<number>(0);
  const activeRef = useRef(active);
  activeRef.current = active;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReduced) return;

    let dpr = window.devicePixelRatio || 1;

    const resize = () => {
      const parent = canvas.parentElement;
      if (!parent) return;
      dpr = window.devicePixelRatio || 1;
      const w = parent.clientWidth;
      const h = parent.clientHeight;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
    };

    resize();
    window.addEventListener("resize", resize);

    // 初始化粒子 — 稀疏分布，约每 8000px² 一个
    const w = canvas.width / dpr;
    const h = canvas.height / dpr;
    const area = w * h;
    const count = Math.min(60, Math.max(20, Math.floor(area / 8000)));
    const particles: Particle[] = [];
    for (let i = 0; i < count; i++) {
      particles.push({
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.3,
        vy: (Math.random() - 0.5) * 0.3,
        r: Math.random() * 1.5 + 0.5,
        opacity: Math.random() * 0.3 + 0.05,
      });
    }
    particlesRef.current = particles;

    const CONNECT_DIST = 120;
    let frame = 0;

    const draw = () => {
      const cw = canvas.width / dpr;
      const ch = canvas.height / dpr;
      ctx.clearRect(0, 0, cw, ch);

      const baseAlpha = activeRef.current ? 0.5 : 0.15;
      const baseConnectAlpha = activeRef.current ? 0.12 : 0.03;

      // 绘制粒子间连线
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < CONNECT_DIST) {
            const alpha = (1 - dist / CONNECT_DIST) * baseConnectAlpha;
            ctx.strokeStyle = `rgba(0, 229, 255, ${alpha})`;
            ctx.lineWidth = 0.5;
            ctx.beginPath();
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.stroke();
          }
        }
      }

      // 绘制粒子（含光晕）
      for (const p of particles) {
        const alpha = baseAlpha + p.opacity * (activeRef.current ? 1.5 : 1);
        const glow = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r * 4);
        glow.addColorStop(0, `rgba(0, 229, 255, ${alpha})`);
        glow.addColorStop(0.4, `rgba(0, 229, 255, ${alpha * 0.4})`);
        glow.addColorStop(1, "rgba(0, 229, 255, 0)");
        ctx.fillStyle = glow;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r * 4, 0, Math.PI * 2);
        ctx.fill();

        // 核心亮点
        ctx.fillStyle = `rgba(0, 229, 255, ${alpha * 0.9})`;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fill();

        // 移动
        p.x += p.vx;
        p.y += p.vy;

        // 边界环绕
        if (p.x < -10) p.x = cw + 10;
        if (p.x > cw + 10) p.x = -10;
        if (p.y < -10) p.y = ch + 10;
        if (p.y > ch + 10) p.y = -10;

        // 每 120 帧微调漂移方向
        if (frame % 120 === 0) {
          p.vx += (Math.random() - 0.5) * 0.1;
          p.vy += (Math.random() - 0.5) * 0.1;
          p.vx = Math.max(-0.5, Math.min(0.5, p.vx));
          p.vy = Math.max(-0.5, Math.min(0.5, p.vy));
        }
      }

      frame++;
      animRef.current = requestAnimationFrame(draw);
    };

    draw();

    return () => {
      cancelAnimationFrame(animRef.current);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: "absolute",
        inset: 0,
        pointerEvents: "none",
        zIndex: 0,
      }}
      aria-hidden="true"
    />
  );
}
