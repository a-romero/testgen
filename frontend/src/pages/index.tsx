import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useProjects } from "../lib/project-context";
import { SimpleTable } from "../components/SimpleTable";

function Stat({ label, value, hint }: { label: string; value: any; hint?: string }) {
  return (
    <div className="card p-4">
      <div className="text-sm text-[rgb(var(--text-secondary))]">{label}</div>
      <div className="text-2xl font-semibold mt-1">{value}</div>
      {hint && <div className="text-xs text-[rgb(var(--text-secondary))] mt-1">{hint}</div>}
    </div>
  );
}

export default function Dashboard() {
  const { current, currentId } = useProjects();
  const [summary, setSummary] = useState<any>(null);
  const [trends, setTrends] = useState<any>(null);
  const [governance, setGovernance] = useState<any>(null);
  const [scope, setScope] = useState<"project" | "all">("project");

  async function load() {
    const pq = scope === "project" && currentId ? `?project_id=${currentId}` : "";
    const [s, t, g] = await Promise.all([
      api(`/dashboard/summary${pq}`),
      api(`/dashboard/trends${pq}`),
      api(`/dashboard/governance`),
    ]);
    setSummary(s);
    setTrends(t);
    setGovernance(g);
  }
  useEffect(() => {
    load();
  }, [currentId, scope]);

  const maxProduced = Math.max(1, ...((trends?.series || []).map((p: any) => p.produced) as number[]));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Dashboard</h1>
          <p className="text-[rgb(var(--text-secondary))]">
            Generation health, quality and adoption {scope === "project" && current ? `for ${current.name}` : "across all projects"}.
          </p>
        </div>
        <select className="input w-48" value={scope} onChange={(e) => setScope(e.target.value as any)}>
          <option value="project">Current project</option>
          <option value="all">All projects</option>
        </select>
      </div>

      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Stat label="Test cases" value={summary.test_cases} />
          <Stat label="Approval rate" value={`${Math.round((summary.approval_rate || 0) * 100)}%`} />
          <Stat label="Avg quality rating" value={summary.avg_rating ?? "—"} hint="from human annotations" />
          <Stat label="Context completeness" value={`${Math.round((summary.context_completeness || 0) * 100)}%`} hint="cases linked to a source doc" />
          <Stat label="Documents" value={summary.documents} hint={`${summary.approved_documents} approved`} />
          <Stat label="Annotation coverage" value={`${Math.round((summary.annotation_coverage || 0) * 100)}%`} />
          <Stat label="Generation runs" value={summary.generation_runs} />
          <Stat label="Generation yield" value={summary.generation_yield != null ? `${Math.round(summary.generation_yield * 100)}%` : "—"} hint="produced vs requested (dedup)" />
        </div>
      )}

      {summary?.status_breakdown && Object.keys(summary.status_breakdown).length > 0 && (
        <div className="card p-6">
          <h2 className="text-lg font-semibold mb-4">Status breakdown</h2>
          <div className="space-y-2">
            {Object.entries(summary.status_breakdown).map(([k, v]: any) => (
              <div key={k} className="flex items-center gap-3">
                <div className="w-32 text-sm text-[rgb(var(--text-secondary))]">{k.replace(/_/g, " ")}</div>
                <div className="flex-1 bg-[rgb(var(--input-bg))] rounded-lg h-5 overflow-hidden">
                  <div className="bg-[rgb(var(--accent))] h-full" style={{ width: `${(v / summary.test_cases) * 100}%` }} />
                </div>
                <div className="w-10 text-right text-sm">{v}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {trends?.series?.length > 0 && (
        <div className="card p-6">
          <h2 className="text-lg font-semibold mb-4">Generation trend</h2>
          <div className="flex items-end gap-2 h-40">
            {trends.series.map((p: any) => (
              <div key={p.date} className="flex flex-col items-center gap-1 flex-1">
                <div className="w-full bg-[rgb(var(--accent))] rounded-t" style={{ height: `${(p.produced / maxProduced) * 100}%` }} title={`${p.produced}`} />
                <div className="text-[10px] text-[rgb(var(--text-secondary))]">{p.date.slice(5)}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="card p-6">
        <h2 className="text-lg font-semibold mb-4">Governance — by market &amp; platform</h2>
        <SimpleTable
          heads={["Market", "Platform", "Total", "Approved", "Rejected", "Approval rate"]}
          rows={(governance?.rows || []).map((r: any) => [
            r.market,
            r.platform,
            String(r.total),
            String(r.approved),
            String(r.rejected),
            `${Math.round((r.approval_rate || 0) * 100)}%`,
          ])}
        />
      </div>
    </div>
  );
}
