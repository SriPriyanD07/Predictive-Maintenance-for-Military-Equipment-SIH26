// React Bits layer: animated number counter for KPI cards. Purposeful, not
// decorative — it draws the eye to a value the instant it changes so an
// operator notices a fleet-count shift without re-reading the whole card.
import { useEffect, useRef } from "react";
import { animate, useMotionValue, useTransform, motion } from "framer-motion";

export function AnimatedCounter({
  value,
  decimals = 0,
  suffix = "",
}: {
  value: number;
  decimals?: number;
  suffix?: string;
}) {
  const motionValue = useMotionValue(0);
  const rounded = useTransform(motionValue, (latest) => latest.toFixed(decimals));
  const hasMounted = useRef(false);

  useEffect(() => {
    const controls = animate(motionValue, value, {
      duration: hasMounted.current ? 0.6 : 0.9,
      ease: "easeOut",
    });
    hasMounted.current = true;
    return controls.stop;
  }, [value, motionValue]);

  return (
    <span className="tabular-nums">
      <motion.span>{rounded}</motion.span>
      {suffix}
    </span>
  );
}
