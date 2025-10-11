export function ScrollArea({ children, className = "", ...props }: any) {
  return <div data-slot="scroll-area" className={`overflow-auto ${className}`} {...props}>{children}</div>
}

