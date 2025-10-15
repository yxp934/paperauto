import React from "react";

type TokenStats = {
  total?: number;
  cost?: number;
  by_agent?: { [k: string]: number };
};

export default function TokenStatsPanel({ stats }: { stats?: TokenStats }) {
  if (!stats) return null;
  const by = stats.by_agent || {};
  return (
    <div className="mt-4 p-3 border rounded-md">
      <h3 className="font-semibold mb-2">Token 使用统计</h3>
      <div className="text-sm text-muted-foreground">总 Token: {stats.total ?? 0}</div>
      <div className="text-sm text-muted-foreground">预估成本: ${Number(stats.cost ?? 0).toFixed(4)}</div>
      <div className="mt-2 grid grid-cols-3 gap-2 text-sm">
        {Object.keys(by).map((k) => (
          <div key={k} className="px-2 py-1 bg-secondary rounded">
            <span className="font-medium mr-1">{k}</span>
            <span>{by[k]}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

