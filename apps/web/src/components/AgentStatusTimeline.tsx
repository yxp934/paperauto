import React, { useMemo } from "react";

type TimelineItem = {
  agent: string;
  start?: number;
  end?: number;
  status?: "running" | "done" | "failed";
};

export default function AgentStatusTimeline({ logs }: { logs: string[] }) {
  const data = useMemo(() => {
    const items: Record<string, TimelineItem> = {};
    const now = Date.now();
    logs.forEach((line) => {
      // Detect tags like [orchestrator], [script_agent], [slide_agent], [qa_agent]
      const m = line.match(/\[(orchestrator|script_agent|slide_agent|qa_agent)\]/);
      if (m) {
        const agent = m[1];
        if (!items[agent]) items[agent] = { agent, start: now, status: "running" };
        // crude end detection
        if (/done|finish|completed|success|succeeded/i.test(line)) {
          items[agent].end = now;
          items[agent].status = "done";
        }
        if (/fail|error|exception/i.test(line)) {
          items[agent].end = now;
          items[agent].status = "failed";
        }
      }
    });
    return Object.values(items);
  }, [logs]);

  if (!data.length) return null;

  return (
    <div className="mt-4 p-3 border rounded-md">
      <h3 className="font-semibold mb-2">Agent 执行状态时间线</h3>
      <ul className="space-y-1 text-sm">
        {data.map((it) => (
          <li key={it.agent} className="flex items-center justify-between">
            <span className="font-medium">[{it.agent}]</span>
            <span className={it.status === "done" ? "text-green-600" : it.status === "failed" ? "text-red-600" : "text-blue-600"}>
              {it.status || "running"}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

