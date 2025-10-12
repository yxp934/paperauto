"use client";
import { useCallback, useEffect, useMemo, useState } from "react";

type RecentJob = { id: string; status: string; created_at?: string };
	export default function DashboardPage() {
  const base = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8001";

  const [jobs, setJobs] = useState<RecentJob[]>([]);
  const [health, setHealth] = useState<"ok"|"error"|"loading">("loading");
  const [latest, setLatest] = useState<{video?: string|null, slides?: string[], subtitle?: string|null}>({});

  const toStatic = useCallback((p?: string|null) => {
    if (!p) return null;
    const rel = p.replace(/^\.?\/??output\/?/, "");
    const encoded = rel.split('/').map(encodeURIComponent).join('/');
    return `${base}/static/${encoded}`;
  }, [base]);

  const refresh = useCallback(async ()=>{
    try {
      const [h, j, o] = await Promise.all([
        fetch(`${base}/api/health`),
        fetch(`${base}/api/jobs/recent`),
        fetch(`${base}/api/outputs/latest`, { cache: 'no-store' })
      ]);
      setHealth(h.ok ? "ok" : "error");
      if (j.ok) setJobs(await j.json());
      if (o.ok) {
        const d = await o.json();
        setLatest({
          video: toStatic(d.video),
          subtitle: toStatic(d.subtitle),
          slides: (d.slides||[]).map((s:string)=> toStatic(s)!).filter(Boolean) as string[],
        });
      }
    } catch { setHealth("error"); }
  }, [base, toStatic]);

  useEffect(()=>{ refresh(); const t = setInterval(refresh, 8000); return ()=>clearInterval(t); }, [refresh]);

  const okDot = (ok: boolean) => <span className={`inline-block w-2 h-2 rounded-full ${ok?"bg-green-500":"bg-red-500"}`} />

  const quickStart = async () => {
    const r = await fetch(`${base}/api/jobs`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode: 'demo', options: { test_mode: true, export_pptx: true } })});
    if (r.ok) refresh();
  }

  return (
    <main className="p-6 space-y-6 max-w-[1200px] mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1>Dashboard</h1>
          <p className="text-muted-foreground mt-1">Overview of recent runs and system status</p>
        </div>
        <div className="flex gap-2">
          <button className="px-3 py-2 rounded-md border" onClick={refresh}>Refresh</button>
          <button className="px-4 py-2 rounded-md bg-primary text-primary-foreground" onClick={quickStart}>Start Demo Job</button>
        </div>
      </div>

      {/* Stats */}
      <section className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="p-4 rounded-md border bg-card" data-slot="card">
          <div className="text-sm text-muted-foreground">API</div>
          <div className="mt-1 flex items-center gap-2"><span className="font-medium">Status</span> {okDot(health==='ok')}</div>
        </div>
        <div className="p-4 rounded-md border bg-card" data-slot="card">
          <div className="text-sm text-muted-foreground">Jobs</div>
          <div className="mt-1 text-2xl font-semibold">{jobs.length}</div>
        </div>
        <div className="p-4 rounded-md border bg-card" data-slot="card">
          <div className="text-sm text-muted-foreground">Latest Result</div>
          <div className="mt-1 text-sm">{latest.video ? 'Video available' : 'No video'}</div>
        </div>
      </section>

      {/* Latest Outputs Preview */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="md:col-span-2 p-4 rounded-md border bg-card" data-slot="card">
          <h2>Latest Video</h2>
          {latest.video ? (
            <video controls className="w-full mt-2 rounded border" src={latest.video || undefined}>
              {latest.subtitle && <track src={latest.subtitle || undefined} kind="subtitles" />}
            </video>
          ) : (
            <div className="h-64 mt-2 rounded bg-muted/30 flex items-center justify-center text-muted-foreground">No video</div>
          )}
        </div>
        <div className="p-4 rounded-md border bg-card" data-slot="card">
          <h2>Latest Slides</h2>
          <div className="grid grid-cols-2 gap-2 mt-2">
            {(latest.slides||[]).slice(0,6).map((s)=> <img key={s} src={s} className="w-full rounded border" alt="slide" />)}
          </div>
        </div>
      </section>

      {/* Recent Jobs */}
      <section className="p-4 rounded-md border bg-card" data-slot="card">
        <h2>Recent Jobs</h2>
        <div className="mt-2 divide-y">
          {jobs.length===0 && <div className="py-4 text-muted-foreground">No recent jobs.</div>}
          {jobs.map(j => (
            <div key={j.id} className="py-2 flex items-center justify-between">
              <div className="text-sm">
                <div className="font-medium">{j.id}</div>
                <div className="text-muted-foreground">{j.created_at || ''}</div>
              </div>
              <div className="px-2 py-1 rounded border text-xs">{j.status}</div>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}

