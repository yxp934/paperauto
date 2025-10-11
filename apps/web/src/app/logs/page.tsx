"use client"
import { useEffect, useRef, useState } from "react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"
import { Pause, Play, RefreshCw } from "lucide-react"

export default function LogsPage() {
  const [jobId, setJobId] = useState(() => {
    if (typeof window !== 'undefined') {
      try {
        const url = new URL(window.location.href)
        return url.searchParams.get('jobId') || ""
      } catch {}
    }
    return ""
  })
  const [logs, setLogs] = useState<string[]>([])
  const [connected, setConnected] = useState(false)
  const [autoScroll, setAutoScroll] = useState(true)
  const wsRef = useRef<WebSocket | null>(null)
  const areaRef = useRef<HTMLDivElement | null>(null)

  async function fetchInitialLogs(id: string) {
    try {
      const httpBase = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8001"
      const token = process.env.NEXT_PUBLIC_API_TOKEN
      const headers = token ? { 'X-API-Token': token } : undefined
      const res = await fetch(`${httpBase}/api/jobs/${id}/logs?limit=200`, { headers })
      if (res.ok) {
        const data = await res.json()
        const items: string[] = (data.logs || []).map((x: any) => (typeof x === 'string' ? x : String(x)))
        setLogs(items)
      }
    } catch {}
  }

  function connect(explicitId?: string) {
    const id = explicitId || jobId
    if (!id) return
    const base = process.env.NEXT_PUBLIC_API_WS_BASE || "ws://127.0.0.1:8001"
    const ws = new WebSocket(`${base}/api/jobs/${id}/ws`)
    wsRef.current = ws
    ws.onopen = () => setConnected(true)
    ws.onclose = () => setConnected(false)
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data)
        if (msg.type === "log" && msg.message) {
          setLogs((prev) => [...prev, String(msg.message)])
        } else if (msg.type === "status") {
          const statusLine = `status: ${msg.status ?? ''}  ${(msg.progress ?? 0) * 100}%  ${msg.message ?? ''}`.trim()
          setLogs((prev) => [...prev, statusLine])
        } else {
          setLogs((prev) => [...prev, ev.data])
        }
      } catch {
        setLogs((prev) => [...prev, ev.data])
      }
    }
    // load latest backlog via REST
    fetchInitialLogs(id)
  }

  // auto-connect when we have a jobId or a query param
  useEffect(() => {
    if (connected || wsRef.current) return
    let id = jobId
    if (typeof window !== 'undefined' && !id) {
      try { id = new URL(window.location.href).searchParams.get('jobId') || '' } catch {}
    }
    if (id) {
      if (!jobId) setJobId(id)
      connect(id)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId, connected])

  useEffect(() => {
    if (!autoScroll) return
    const el = areaRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
  }, [logs, autoScroll])

  // try to hydrate jobId from URL (?jobId=...) on first mount
  useEffect(() => {
    (async () => {
      try {
        const url = new URL(window.location.href)
        const id = url.searchParams.get('jobId')
        if (id) {
          setJobId(id)
          return
        }
      } catch {}
      // fall back to latest recent job
      try {
        const httpBase = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8001"
        const token = process.env.NEXT_PUBLIC_API_TOKEN
        const headers = token ? { 'X-API-Token': token } : undefined
        const res = await fetch(`${httpBase}/api/jobs/recent?limit=1`, { headers })
        if (res.ok) {
          const data = await res.json()
          const latest = (data.job_ids || [])[0]
          if (latest) setJobId(latest)
        }
      } catch {}
    })()
  }, [])

  return (
    <main className="p-8 max-w-[1400px] mx-auto">
      <div className="mb-8">
        <h1>Logs</h1>
        <p className="text-muted-foreground mt-1">Live log viewer for pipeline jobs</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="space-y-4">
          <Card className="p-4">
            <h3 className="mb-4">Job Selection</h3>
            <div className="space-y-2">
              <Label>Job ID</Label>
              <Input value={jobId} onChange={(e) => setJobId(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') connect() }} placeholder="run-001" />
            </div>
          </Card>
          <Card className="p-4">
            <h3 className="mb-4">Actions</h3>
            <div className="space-y-2">
              <Button variant="outline" className="w-full justify-start" onClick={() => setAutoScroll(!autoScroll)}>
                {autoScroll ? (
                  <>
                    <Pause className="h-4 w-4 mr-2" /> Pause Live
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4 mr-2" /> Resume Live
                  </>
                )}
              </Button>
              <Button variant="outline" className="w-full justify-start" onClick={() => setLogs([])}>
                <RefreshCw className="h-4 w-4 mr-2" /> Clear
              </Button>
              <Button className="w-full" onClick={() => connect()} disabled={!jobId}>
                Connect
              </Button>
              {connected && <Badge variant="secondary">connected</Badge>}
            </div>
          </Card>
        </div>

        <div className="lg:col-span-3">
          <Card className="p-6">
            <div className="flex items-center justify-between mb-4">
              <h2>Live Logs {jobId && `- ${jobId}`}</h2>
              {connected && (
                <Badge variant="secondary" className="gap-1">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                  </span>
                  Live
                </Badge>
              )}
            </div>
            <ScrollArea className="h-[70vh] rounded-md border bg-muted/30 p-4" ref={areaRef as any}>
              <div className="space-y-2 font-mono text-xs">
                {logs.map((line, idx) => (
                  <div key={idx} className="flex gap-3 items-start">
                    <span className="flex-1 whitespace-pre-wrap">{line}</span>
                  </div>
                ))}
              </div>
            </ScrollArea>
          </Card>
        </div>
      </div>
    </main>
  )
}

