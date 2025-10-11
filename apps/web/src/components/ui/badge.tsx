export function Badge({ children, className = "" }: { children?: React.ReactNode; className?: string }) {
  return <span data-slot="badge" className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs ${className}`}>{children}</span>
}

