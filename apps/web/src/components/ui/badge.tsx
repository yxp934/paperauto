import { cn } from "./utils";

export type BadgeVariant = "default" | "secondary" | "destructive" | "outline";

export function Badge({ children, className = "", variant = "default" }: { children?: React.ReactNode; className?: string; variant?: BadgeVariant }) {
  const variantClasses: Record<BadgeVariant, string> = {
    default: "bg-primary text-primary-foreground border-transparent",
    secondary: "bg-secondary text-secondary-foreground border-transparent",
    destructive: "bg-destructive text-destructive-foreground border-transparent",
    outline: "border-border text-foreground",
  };
  return (
    <span
      data-slot="badge"
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs border",
        variantClasses[variant],
        className
      )}
    >
      {children}
    </span>
  );
}

