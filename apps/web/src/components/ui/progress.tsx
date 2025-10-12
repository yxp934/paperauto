import { cn } from "./utils";

export function Progress({ value = 0, className = "" }: { value?: number; className?: string }) {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div className={cn("w-full h-2 bg-muted rounded-full overflow-hidden", className)}>
      <div className="h-full bg-primary" style={{ width: `${clamped}%` }} />
    </div>
  );
}

