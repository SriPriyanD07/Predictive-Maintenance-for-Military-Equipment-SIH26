// OriginKit layer: consistent button states (primary/ghost/danger) reused
// across the alert panel actions and modal footer.
import type { ButtonHTMLAttributes } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "ghost" | "danger" | "subtle";
  size?: "sm" | "md";
}

const VARIANT_CLASSES: Record<NonNullable<ButtonProps["variant"]>, string> = {
  primary: "bg-status-info text-base-950 hover:bg-status-info/90 border-transparent",
  ghost: "bg-transparent text-ink-300 hover:bg-base-800 border-base-700",
  danger: "bg-status-critical/90 text-white hover:bg-status-critical border-transparent",
  subtle: "bg-base-800 text-ink-100 hover:bg-base-700 border-base-700",
};

const SIZE_CLASSES: Record<NonNullable<ButtonProps["size"]>, string> = {
  sm: "px-2.5 py-1 text-xs",
  md: "px-3.5 py-1.5 text-sm",
};

export function Button({ variant = "subtle", size = "md", className = "", ...props }: ButtonProps) {
  return (
    <button
      className={`inline-flex items-center gap-1.5 rounded-md border font-medium transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-50 ${VARIANT_CLASSES[variant]} ${SIZE_CLASSES[size]} ${className}`}
      {...props}
    />
  );
}
