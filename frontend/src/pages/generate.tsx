import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import { api } from "../lib/api";
import { useProjects } from "../lib/project-context";
import { Document, Template, TestCase } from "../lib/types";

export default function GeneratePage() {
  const { current, currentId } = useProjects();
  const router = useRouter();
  const [templates, setTemplates] = useState<Template[]>([]);
  const [docs, setDocs] = useState<Document[]>([]);
  const [templateId, setTemplateId] = useState("");
  const [docIds, setDocIds] = useState<string[]>([]);
  const [numCases, setNumCases] = useState(5);
  const [requireApproved, setRequireApproved] = useState(false);
  const [extra, setExtra] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<TestCase[] | null>(null);

  async function load() {
    if (!currentId) return;
    const [t, d] = await Promise.all([
      api<Template[]>(`/templates?project_id=${currentId}`),
      api<Document[]>(`/documents?project_id=${currentId}`),
    ]);
    setTemplates(t);
    setDocs(d);
    setTemplateId((prev) => prev || t[0]?.id || "");
  }
  useEffect(() => {
    load();
    setResult(null);
  }, [currentId]);

  function toggleDoc(id: string) {
    setDocIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }

  async function generate() {
    if (!templateId) {
      alert("Select a template");
      return;
    }
    setBusy(true);
    setResult(null);
    try {
      const res = await api<TestCase[]>("/testcases/generate", "POST", {
        project_id: currentId,
        template_id: templateId,
        document_ids: docIds,
        num_cases: numCases,
        require_approved_documents: requireApproved,
        extra_instructions: extra,
      });
      setResult(res);
    } catch (e: any) {
      alert(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (!currentId)
    return <div className="card p-8 text-center text-[rgb(var(--text-secondary))]">Create a project first.</div>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Generate test cases</h1>
        <p className="text-[rgb(var(--text-secondary))]">
          Produce unique BDD scenarios for <span className="text-[rgb(var(--text))] font-medium">{current?.name}</span>. Duplicates are automatically suppressed.
        </p>
      </div>

      <div className="card p-6 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="label">Template</label>
            <select className="input" value={templateId} onChange={(e) => setTemplateId(e.target.value)}>
              <option value="">Select…</option>
              {templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Number of cases</label>
            <input className="input" type="number" min={1} max={50} value={numCases} onChange={(e) => setNumCases(Number(e.target.value))} />
          </div>
          <div className="flex items-end">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={requireApproved} onChange={(e) => setRequireApproved(e.target.checked)} />
              Only use approved documents
            </label>
          </div>
        </div>

        <div>
          <label className="label">Source requirements documents</label>
          {docs.length === 0 ? (
            <p className="text-sm text-[rgb(var(--text-secondary))]">No documents — add some under Requirements.</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-1">
              {docs.map((d) => (
                <label key={d.id} className="flex items-center gap-2 text-sm border border-[rgb(var(--border))] rounded-lg px-3 py-2">
                  <input type="checkbox" checked={docIds.includes(d.id)} onChange={() => toggleDoc(d.id)} />
                  <span className="flex-1">{d.title} <span className="badge ml-1">v{d.version}</span></span>
                  <span className={d.status === "approved" ? "success text-xs" : "text-[rgb(var(--text-secondary))] text-xs"}>{d.status}</span>
                </label>
              ))}
            </div>
          )}
        </div>

        <div>
          <label className="label">Extra instructions (optional)</label>
          <input className="input" value={extra} onChange={(e) => setExtra(e.target.value)} placeholder="e.g. focus on negative paths and accessibility" />
        </div>

        <button className="btn btn-primary" onClick={generate} disabled={busy || !templateId}>
          {busy ? "Generating…" : `Generate ${numCases} test cases`}
        </button>
      </div>

      {result && (
        <div className="card p-6 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Generated {result.length} unique test case{result.length === 1 ? "" : "s"}</h2>
            <button className="btn" onClick={() => router.push("/testcases")}>Review &amp; approve →</button>
          </div>
          {result.map((tc) => (
            <div key={tc.id} className="border border-[rgb(var(--border))] rounded-xl p-3">
              <div className="font-medium mb-1">{tc.title} <span className="badge ml-2">{tc.priority}</span></div>
              <pre className="whitespace-pre-wrap text-sm">{tc.gherkin}</pre>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
