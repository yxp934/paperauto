"use client";
import { useEffect, useState } from "react";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";

export default function ResultsPage() {
  const [jobs, setJobs] = useState<string[]>([]);
  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8001";
    fetch(`${base}/api/jobs/recent`).then(r => r.json()).then(d => setJobs(d.jobs || [])).catch(() => setJobs([]));
  }, []);
  return (
    <div className="space-y-4">
      <h1>Results</h1>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button className="bg-secondary text-secondary-foreground">Recent jobs</Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          {jobs.length ? jobs.map(id => (
            <DropdownMenuItem key={id}>{id}</DropdownMenuItem>
          )) : (
            <DropdownMenuItem disabled>No jobs</DropdownMenuItem>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}

