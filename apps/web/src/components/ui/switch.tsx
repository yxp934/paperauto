"use client";
import { cn } from "./utils";

export function Switch({ checked, onCheckedChange, className = "", disabled }: { checked: boolean; onCheckedChange: (checked: boolean) => void; className?: string; disabled?: boolean; }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => !disabled && onCheckedChange(!checked)}
      className={cn(
        "relative inline-flex h-5 w-9 items-center rounded-full border transition-colors",
        checked ? "bg-primary" : "bg-switch-background",
        disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer",
        className
      )}
    >
      <span
        className={cn(
          "inline-block h-4 w-4 transform rounded-full bg-white transition-transform",
          checked ? "translate-x-[calc(100%-2px)]" : "translate-x-0",
          "ml-[2px]"
        )}
      />
    </button>
  );
}

