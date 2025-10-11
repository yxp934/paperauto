export function Card({ className = "", children }: { className?: string; children?: React.ReactNode }) {
  return <div data-slot="card" className={`rounded-md border bg-white ${className}`}>{children}</div>
}

