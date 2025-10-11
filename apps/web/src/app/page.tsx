"use client"
import { useEffect, useState } from "react"

export default function Home() {
  const [status, setStatus] = useState<string>("loading…")

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8001"
    fetch(`${base}/api/health`).then(async (res) => {
      if (!res.ok) throw new Error(String(res.status))
      const data = await res.json()
      setStatus(`backend: ${data.status || "unknown"}`)
    }).catch((e) => setStatus(`backend: error (${e.message})`))
  }, [])

  return (
    <main style={{ padding: 24 }}>
      <h1>Video Generation UI</h1>
      <p style={{ marginTop: 8 }}>Health check: {status}</p>
      <p style={{ marginTop: 8, color: "#666" }}>
        NEXT_PUBLIC_API_BASE={process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8001"}
      </p>
    </main>
  )
}

