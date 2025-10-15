"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import TokenStatsPanel from "@/components/TokenStatsPanel";
import AgentStatusTimeline from "@/components/AgentStatusTimeline";
import RegenerateButton from "@/components/RegenerateButton";

type Mode = "demo" | "complete" | "single" | "slides";

type JobStatus = {
  id: string
  status: string
  progress?: number
  message?: string
  result?: any
}

export default function GeneratePage() {
  const base = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";
  const wsBase = useMemo(() => {
    const env = process.env.NEXT_PUBLIC_API_WS_BASE;
    if (env) return env;
    try {
      const u = new URL(base);
      u.protocol = u.protocol === "https:" ? "wss:" : "ws:";
      return u.origin;
    } catch { return "ws://127.0.0.1:8000"; }
  }, [base]);

  const [mode, setMode] = useState<Mode>("demo");
  const [paperId, setPaperId] = useState<string>("");
  const [maxPapers, setMaxPapers] = useState<number>(1);
  const [testMode, setTestMode] = useState<boolean>(true);
  const [exportPptx, setExportPptx] = useState<boolean>(true);
  const [uploadVideo, setUploadVideo] = useState<boolean>(false);
  const [useA2A, setUseA2A] = useState<boolean>(false);

  const [job, setJob] = useState<JobStatus | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [connecting, setConnecting] = useState(false);
  const [recentPaper, setRecentPaper] = useState<{id?: string, title?: string, url?: string, authors?: string[]}>({});
  const [tokenStats, setTokenStats] = useState<{ total?: number, cost?: number, by_agent?: Record<string, number> }>();
  const wsRef = useRef<WebSocket | null>(null);

  const toStatic = (p?: string | null) => {
    if (!p) return null;
    const rel = p.replace(/^\.?\/??output\/?/, "");
    const encoded = rel.split('/').map(encodeURIComponent).join('/');
    return `${base}/static/${encoded}`;
  };

  const startJob = useCallback(async () => {
    setLogs([]);
    setJob(null);
    setTokenStats(undefined);
    const body: any = { mode };
    if (mode === "single" || mode === "slides") body.paper_id = paperId || "2510.03215";
    if (mode === "complete") body.options = { max_papers: maxPapers, test_mode: testMode, export_pptx: exportPptx, upload_video: uploadVideo, use_a2a: useA2A };
    if (mode === "demo") body.options = { test_mode: testMode, export_pptx: exportPptx, upload_video: uploadVideo };
    if (mode === "single" || mode === "slides") body.options = { test_mode: testMode, export_pptx: exportPptx, upload_video: uploadVideo };

    const res = await fetch(`${base}/api/jobs`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!res.ok) throw new Error(`Create job failed: ${res.status}`);
    const data = await res.json();
    const id = data.job_id || data.id || data?.job?.id || data?.id;
    setJob({ id, status: "queued", progress: 0 });
    setTimeout(() => connectWS(id), 50);
  }, [mode, paperId, maxPapers, testMode, exportPptx, uploadVideo, useA2A, base]);

  const connectWS = useCallback((id: string) => {
    try { wsRef.current?.close(); } catch {}
    const url = `${wsBase}/api/jobs/${id}/ws`;
    setConnecting(true);
    const ws = new WebSocket(url);
    wsRef.current = ws;
    ws.onopen = () => {
      setConnecting(false);
      // Ask server to replay latest paper event over WS so tests can observe it
      try { fetch(`${base}/api/jobs/${id}/replay-paper`, { method: 'POST' }); } catch {}
    };
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data as string);
        if (msg?.type === "log" && msg?.message) setLogs((prev) => [...prev, String(msg.message)]);
        if (msg?.type === "status") {
          const nextStatus = msg.status === 'done' ? 'succeeded' : msg.status;
          setJob((j) => j ? { ...j, status: nextStatus, progress: msg.progress, message: msg.message, result: msg.result || j.result } : j);
          if (['succeeded','failed','cancelled'].includes(nextStatus)) {
            // pull latest outputs as soon as WS signals completion
            (async () => { try { await refreshLatest(); } catch {} })();
          }
        }
        if (msg?.type === "progress") setJob((j) => j ? { ...j, status: j.status || "running", progress: typeof msg.progress === 'number' ? msg.progress : j.progress, message: msg.message || msg.stage || j.message } : j);
        if (msg?.type === "paper") setRecentPaper({ id: msg.id, title: msg.title, url: msg.url, authors: msg.authors });
        if (msg?.type === "token") setTokenStats({ total: msg.total, cost: msg.cost, by_agent: msg.by_agent });
      } catch {
        setLogs((prev) => [...prev, String(e.data)]);
      }
    };
    ws.onclose = () => setConnecting(false);
  }, [wsBase]);

  useEffect(() => () => { try { wsRef.current?.close(); } catch {} }, []);

  const [latest, setLatest] = useState<{video?: string|null, subtitle?: string|null, slides?: string[], pptx?: string|null}>({});
  const refreshLatest = useCallback(async () => {
    const r = await fetch(`${base}/api/outputs/latest`, { cache: "no-store" });
    if (r.ok) {
      const d = await r.json();
      setLatest({
        video: toStatic(d.video),
        subtitle: toStatic(d.subtitle),
        slides: (d.slides||[]).map((p:string)=> toStatic(p)!).filter(Boolean) as string[],
        pptx: toStatic(d.pptx)
      });
    }
  }, [base]);

  useEffect(() => {
    let t: any;
    if (job && ["running","queued"].includes(job.status)) {
      t = setInterval(async () => {
        const r = await fetch(`${base}/api/jobs/${job.id}`);
        if (r.ok) {
          const d = await r.json();
          setJob((j)=> j ? { ...j, status: d.status, progress: d.progress, message: d.message, result: d.result||j.result } : j);
          if (["succeeded","failed","cancelled"].includes(d.status)) {
            clearInterval(t); await refreshLatest();
          }
        }
      }, 2000);
    }
    return () => t && clearInterval(t);
  }, [job?.id, job?.status, base, refreshLatest]);

  // Fallback: poll logs REST to ensure log pane shows even if WS delayed
  useEffect(() => {
    if (!job?.id) return;
    let stopped = false;
    let t: any;
    const poll = async () => {
      try {
        const r = await fetch(`${base}/api/jobs/${job.id}/logs?limit=200`, { cache: 'no-store' });
        if (r.ok) {
          const d = await r.json();
          const text = (d.logs || []).join('\n');
          setLogs(text ? text.split(/\n/) : []);
        }
      } catch {}
      if (!stopped && (job.status === 'running' || job.status === 'queued')) t = setTimeout(poll, 1000);
    };
    poll();
    return () => { stopped = true; if (t) clearTimeout(t); };
  }, [job?.id, job?.status, base]);

  return (
    <main className="p-6 max-w-[1200px] mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1>Generate</h1>
          <p className="text-muted-foreground mt-1">Configure and run the video generation pipeline</p>
        </div>
        <button className="px-4 py-2 rounded-md bg-primary text-primary-foreground disabled:opacity-50" onClick={startJob} disabled={connecting || (job && ["running","queued"].includes(job.status))}>
          {job && ["running","queued"].includes(job.status) ? "Running…" : "Start Pipeline"}
        </button>
      </div>

      {/* Form */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="md:col-span-2 space-y-4 p-4 rounded-md border bg-card">
          <h2>Mode</h2>
          <div className="flex flex-wrap gap-2">
            {(["demo","complete","single","slides"] as Mode[]).map(m => (
              <button key={m} className={`px-3 py-1.5 rounded border ${mode===m?"bg-sidebar-accent text-sidebar-accent-foreground border-sidebar-accent":"bg-input-background"}`} onClick={()=>setMode(m)}>
                {m}
              </button>
            ))}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
            {(mode==="single"||mode==="slides") && (
              <div>
                <label className="text-sm text-muted-foreground">paper_id</label>
                <input value={paperId} onChange={e=>setPaperId(e.target.value)} placeholder="2510.03215" className="mt-1 w-full rounded-md border px-3 py-2 bg-input-background" />
              </div>
            )}
            {mode==="complete" && (
              <div>
                <label className="text-sm text-muted-foreground">max_papers</label>
                <input type="number" min={1} max={5} value={maxPapers} onChange={e=>setMaxPapers(parseInt(e.target.value||'1'))} className="mt-1 w-full rounded-md border px-3 py-2 bg-input-background" />
              </div>
            )}
            <div className="flex items-center gap-2">
              <input id="test_mode" type="checkbox" checked={testMode} onChange={e=>setTestMode(e.target.checked)} />
              <label htmlFor="test_mode">test_mode</label>
            </div>
            <div className="flex items-center gap-2">
              <input id="export_pptx" type="checkbox" checked={exportPptx} onChange={e=>setExportPptx(e.target.checked)} />
              <label htmlFor="export_pptx">export_pptx</label>
            </div>
            <div className="flex items-center gap-2">
              <input id="upload_video" type="checkbox" checked={uploadVideo} onChange={e=>setUploadVideo(e.target.checked)} />
              <label htmlFor="upload_video">upload_video</label>
            </div>
            <div className="flex items-center gap-2">
              <input id="use_a2a" type="checkbox" checked={useA2A} onChange={e=>setUseA2A(e.target.checked)} />
              <label htmlFor="use_a2a">使用 A2A</label>
            </div>

          </div>
        </div>

        {/* Live status */}
        <div className="space-y-3 p-4 rounded-md border bg-card">
          <h2>Status</h2>
          <div className="text-sm">Job: {job?.id || "-"}</div>
          <div className="text-sm">State: {job?.status || "-"} {typeof job?.progress === 'number' ? `• ${(job!.progress!*100).toFixed(0)}%` : ''}</div>
          <div className="w-full h-2 bg-muted/30 rounded">
            <div className="h-2 bg-primary rounded" style={{ width: `${Math.max(0, Math.min(100, (job?.progress||0)*100))}%` }} />
          </div>
          <TokenStatsPanel stats={tokenStats} />
        </div>
      </section>

      {/* Logs + Recent Paper */}
      <section className="p-4 rounded-md border bg-card">
        <h2>Live Logs</h2>
        <div className="mt-2 h-64 overflow-auto rounded bg-muted/30 p-2 text-sm font-mono whitespace-pre-wrap">
          {logs.length ? logs.join("\n") : "No logs yet."}
        </div>
        <AgentStatusTimeline logs={logs} />
        {recentPaper?.title && (
          <div className="mt-3 px-3 py-2 rounded border text-sm bg-input-background">
            <div className="font-medium truncate max-w-[480px]" title={recentPaper.title}>{recentPaper.title}</div>
            <div className="text-muted-foreground truncate max-w-[480px]">{recentPaper.id} {recentPaper.authors?.length ? `• ${recentPaper.authors.join(', ')}` : ''}</div>
            {recentPaper.url && <a className="text-primary underline" href={recentPaper.url} target="_blank" rel="noreferrer">arXiv</a>}
          </div>
        )}
      </section>

      {/* Results */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="md:col-span-2 p-4 rounded-md border bg-card">
          <h2>Video</h2>
          {latest.video ? (
            <video controls className="w-full mt-2 rounded border" src={latest.video || undefined}>
              {latest.subtitle && <track src={latest.subtitle || undefined} kind="subtitles" />}
            </video>
          ) : (
            <div className="h-64 mt-2 rounded bg-muted/30 flex items-center justify-center text-muted-foreground">No video</div>
          )}
          <div className="flex gap-2 mt-3">
            {latest.video && <a className="px-3 py-1.5 rounded border" href={latest.video} download>Download Video</a>}
            {latest.subtitle && <a className="px-3 py-1.5 rounded border" href={latest.subtitle} download>Download Subtitles</a>}
            {latest.pptx && <a className="px-3 py-1.5 rounded border" href={latest.pptx} download>Download PPTX</a>}
            <RegenerateButton jobId={job?.id} base={base} />
          </div>
        </div>
        <div className="p-4 rounded-md border bg-card">
          <h2>Slides</h2>
          <div className="grid grid-cols-2 gap-2 mt-2">
            {(latest.slides||[]).map(s => (
              <div key={s} className="relative group">
                <img src={s} className="w-full rounded border" alt="slide" />
                <a href={s} download className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition px-2 py-1 text-xs bg-black/60 text-white rounded">Download</a>
              </div>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}

