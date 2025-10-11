"use client"
export function Button({ className = "", children, ...props }: any) {
  return <button className={`inline-flex items-center justify-center rounded-md border px-3 py-2 ${className}`} {...props}>{children}</button>
}

