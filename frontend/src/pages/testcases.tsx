import { useEffect, useState } from "react";
import { api, base, download } from "../lib/api";
import { useProjects } from "../lib/project-context";
import { StatusBadge } from "../components/SimpleTable";
import { TestCase } from "../lib/types";

const STATUS_FILTERS = ["all", "generated", "pending_review", "needs_changes", "approved", "rejected"];

export default function TestCasesPage() {
  const { current, currentId } = useProjects();
  const [cases, setCases] = useState<TestCase[]>([]);
  const [filter, setFilter] = useState("all");
  const [exportFmt, setExportFmt] = useState("gherkin");

  async function load() {
    if (!currentId) return;
    const q = filter === "all" ? "" : `&status=${filter}`;
    setCases(await api<TestCase[]>(`/testcases?project_id=${currentId}${q}`));
  }
  useEffect(() => {
    load();
  }, [currentId, filter]);

  async function annotate(tc: TestCase, verdict: string) {
    const comment = prompt(`Annotation (${verdict}) — optional comment`) ?? "";
    const ratingStr = verdict === "valid" ? prompt("Quality rating 1-5 (optional)") : null;
    const rating = ratingStr ? Number(ratingStr) : null;
    await api(`/testcases/${tc.id}/annotations`, "POST", { author: "qa", verdict, comment, rating });
    await load();
  }
  async function approve(tc: TestCase, ok: boolean) {
    const comment = ok ? "" : prompt("Reason for rejection (optional)") ?? "";
    await api(`/testcases/${tc.id}/approve`, "POST", { approved_by: "qa-lead", approve: ok, comment });
    await load();
  }
  async function regenerate(tc: TestCase) {
    const feedback = prompt("Feedback for regeneration (the model/template will revise this case):");
    if (!feedback) return;
    await api(`/testcases/${tc.id}/regenerate`, "POST", { feedback, author: "qa" });
    await load();
  }
  async function remove(tc: TestCase) {
    if (!confirm("Delete this test case?")) return;
    await api(`/testcases/${tc.id}`, "DELETE");
    await load();
  }
  async function doExport() {
    const ext = exportFmt === "gherkin" ? "feature" : exportFmt === "json" ? "json" : "csv";
    await download(`/testcases/export/${currentId}?format=${exportFmt}`, `testcases.${ext}`);
  }

  if (!currentId)
    return <div className="card p-8 text-center text-[rgb(var(--text-secondary))]">Create a project first.</div>;

  const counts = STATUS_FILTERS.reduce((acc, s) => {
    acc[s] = s === "all" ? cases.length : cases.filter((c) => c.status === s).length;
    return acc;
  }, {} as Record<string, number>);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Review &amp; Approve</h1>
          <p className="text-[rgb(var(--text-secondary))]">
            Validate generated BDD test cases for {current?.name} with human annotations and an approval workflow.
          </p>
        </div>
        <div className="flex items-end gap-2">
          <div>
            <label className="label">Export</label>
            <select className="input" value={exportFmt} onChange={(e) => setExportFmt(e.target.value)}>
              <option value="gherkin">Gherkin (.feature)</option>
              <option value="csv">CSV</option>
              <option value="json">JSON</option>
              <option value="jira">Jira / ADO CSV</option>
            </select>
          </div>
          <button className="btn" onClick={doExport}>Export</button>
        </div>
      </div>

      <div className="flex gap-2 flex-wrap">
        {STATUS_FILTERS.map((s) => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={`px-3 py-1.5 rounded-lg text-sm border ${
              filter === s ? "bg-[rgb(var(--accent))] text-white border-[rgb(var(--accent))]" : "border-[rgb(var(--border))] hover:bg-[rgb(var(--hover))]"
            }`}
          >
            {s.replace(/_/g, " ")} ({counts[s] ?? 0})
          </button>
        ))}
      </div>

      <div className="space-y-3">
        {cases.length === 0 && (
          <div className="card p-8 text-center text-[rgb(var(--text-secondary))]">
            No test cases. Generate some from the Generate page.
          </div>
        )}
        {cases.map((tc) => (
          <div key={tc.id} className="card p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  <span className="font-medium">{tc.title}</span>
                  <StatusBadge status={tc.status} />
                  <span className="badge">{tc.priority}</span>
                  <span className="badge">{tc.test_phase}</span>
                  {(tc.market || tc.platform) && <span className="badge">{[tc.market, tc.platform].filter(Boolean).join("/")}</span>}
                </div>
                <pre className="whitespace-pre-wrap text-sm bg-[rgb(var(--input-bg))] rounded-lg p-3">{tc.gherkin}</pre>
                {tc.test_techniques?.length > 0 && (
                  <div className="text-xs text-[rgb(var(--text-secondary))] mt-1">techniques: {tc.test_techniques.join(", ")}</div>
                )}
                {tc.annotations?.length > 0 && (
                  <div className="mt-2 space-y-1">
                    {tc.annotations.map((a) => (
                      <div key={a.id} className="text-xs border-l-2 border-[rgb(var(--accent))] pl-2">
                        <span className="font-medium">{a.author}</span> · {a.verdict}
                        {a.rating ? ` · ${a.rating}★` : ""} {a.comment && `— ${a.comment}`}
                      </div>
                    ))}
                  </div>
                )}
                {tc.regeneration_history?.length > 0 && (
                  <div className="text-xs text-[rgb(var(--text-secondary))] mt-1">
                    regenerated {tc.regeneration_history.length} time(s)
                  </div>
                )}
              </div>
            </div>
            <div className="flex gap-2 mt-3 flex-wrap">
              <button className="btn btn-sm btn-primary" onClick={() => approve(tc, true)}>Approve</button>
              <button className="btn btn-sm" onClick={() => approve(tc, false)}>Reject</button>
              <button className="btn btn-sm" onClick={() => annotate(tc, "valid")}>Mark valid</button>
              <button className="btn btn-sm" onClick={() => annotate(tc, "needs_changes")}>Needs changes</button>
              <button className="btn btn-sm" onClick={() => regenerate(tc)}>Regenerate w/ feedback</button>
              <button className="btn btn-sm" onClick={() => remove(tc)}>Delete</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
