export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={`rounded-md border px-2 py-1 ${props.className || ""}`} />
}

