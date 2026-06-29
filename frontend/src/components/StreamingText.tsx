import { useEffect, useRef, useState } from "react";

interface Props {
  text: string;
}

export default function StreamingText({ text }: Props) {
  const [displayed, setDisplayed] = useState("");
  const rafRef = useRef<number>(0);
  const lastTime = useRef(0);

  useEffect(() => {
    if (text.length - displayed.length > 20) {
      // batch update for performance
      const step = () => {
        const now = Date.now();
        if (now - lastTime.current > 16) {
          // ~60fps
          setDisplayed(text);
          lastTime.current = now;
        }
        rafRef.current = requestAnimationFrame(step);
      };
      rafRef.current = requestAnimationFrame(step);
    } else {
      setDisplayed(text);
    }
    return () => cancelAnimationFrame(rafRef.current);
  }, [text, displayed.length]);

  return <>{displayed || text}</>;
}
