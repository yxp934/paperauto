import React, { useState } from "react";

export default function RegenerateButton({ jobId, base }:{ jobId?: string, base: string }) {
  const [scope, setScope] = useState<'script'|'slide'|'all'>('all');
  const [index, setIndex] = useState<number|''>('');
  const [loading, setLoading] = useState(false);

  const onClick = async () => {
    if (!jobId) return;
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (scope) params.set('scope', scope);
      if (index !== '' && Number(index) > 0) params.set('index', String(index));
      const r = await fetch(`${base}/api/jobs/${jobId}/regenerate?${params.toString()}`, { method: 'POST' });
      if (!r.ok) throw new Error(await r.text());
    } catch (e) {
      console.error('Regenerate failed', e);
      alert('重新生成失败: ' + (e as any)?.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mt-4 flex items-center gap-2">
      <label className="text-sm">范围</label>
      <select className="border rounded px-2 py-1" value={scope} onChange={e=>setScope(e.target.value as any)}>
        <option value="script">script</option>
        <option value="slide">slide</option>
        <option value="all">all</option>
      </select>
      <label className="text-sm">索引</label>
      <input className="border rounded px-2 py-1 w-20" placeholder="1" value={index} onChange={e=>setIndex(e.target.value? Number(e.target.value): '')} />
      <button className="px-3 py-1 bg-blue-600 text-white rounded" onClick={onClick} disabled={!jobId || loading}>
        {loading ? '重新生成中...' : '重新生成'}
      </button>
    </div>
  );
}

