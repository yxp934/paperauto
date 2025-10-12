"use client";
import { cn } from "./utils";

export function Dialog({ open, onOpenChange, children }: { open: boolean; onOpenChange?: (open: boolean) => void; children: React.ReactNode }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-black/60" onClick={() => onOpenChange?.(false)} />
      {children}
    </div>
  );
}

export function DialogContent({ className = "", children }: { className?: string; children?: React.ReactNode }) {
  return (
    <div className={cn("absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 bg-card text-card-foreground rounded-lg shadow-lg w-[90vw] max-w-xl p-6", className)}>
      {children}
    </div>
  );
}

export function DialogHeader({ children }: { children?: React.ReactNode }) {
  return <div className="mb-4">{children}</div>;
}

export function DialogTitle({ children }: { children?: React.ReactNode }) {
  return <h3 className="text-lg font-semibold">{children}</h3>;
}

export function DialogDescription({ children }: { children?: React.ReactNode }) {
  return <p className="text-sm text-muted-foreground">{children}</p>;
}

