import { useEffect, useState } from "react";
import { api, base } from "../lib/api";
import { useProjects } from "../lib/project-context";
import { SimpleTable, StatusBadge } from "../components/SimpleTable";
import { Document } from "../lib/types";

export default function DocumentsPage() {
  const { current, currentId } = useProjects();
  const [docs, setDocs] = useState<Document[]>([]);
  const [form, setForm] = useState({ title: "", content: "", doc_type: "requirements" });
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [viewing, setViewing] = useState<Document | null>(null);

  async function load() {
    if (!currentId) return;
    setDocs(await api<Document[]>(`/documents?project_id=${currentId}`));
  }
  useEffect(() => {
    load();
  }, [currentId]);

  async function create() {
    if (!currentId || !form.title.trim()) return;
    setBusy(true);
    try {
      if (file) {
        const fd = new FormData();
        fd.append("project_id", currentId);
        fd.append("title", form.title);
        fd.append("doc_type", form.doc_type);
        fd.append("market", current?.market || "");
        fd.append("platform", current?.platform || "");
        fd.append("file", file);
        await api("/documents/upload", "POST", fd);
      } else {
        await api("/documents", "POST", {
          project_id: currentId,
          title: form.title,
          content: form.content,
          doc_type: form.doc_type,
          market: current?.market || "",
          platform: current?.platform || "",
        });
      }
      setForm({ title: "", content: "", doc_type: "requirements" });
      setFile(null);
      await load();
    } catch (e: any) {
      alert(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function approve(id: string) {
    await api(`/documents/${id}/approve?approved_by=qa-lead`, "POST");
    await load();
  }
  async function newVersion(d: Document) {
    const content = prompt("New version content", d.content);
    if (content == null) return;
    await api(`/documents/${d.id}/versions`, "POST", {
      project_id: d.project_id,
      title: d.title,
      content,
      doc_type: d.doc_type,
      market: d.market,
      platform: d.platform,
    });
    await load();
  }
  async function remove(id: string) {
    if (!confirm("Delete this document version?")) return;
    await api(`/documents/${id}`, "DELETE");
    await load();
  }

  if (!currentId) return <Empty />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Requirements & Context</h1>
        <p className="text-[rgb(var(--text-secondary))]">
          Upload, version and approve the requirements that drive generation for{" "}
          <span className="text-[rgb(var(--text))] font-medium">{current?.name}</span>.
        </p>
      </div>

      <div className="card p-6 space-y-4">
        <h2 className="text-lg font-semibold">Add requirements document</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="label">Title</label>
            <input className="input" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
          </div>
          <div>
            <label className="label">Type</label>
            <select className="input" value={form.doc_type} onChange={(e) => setForm({ ...form, doc_type: e.target.value })}>
              <option value="requirements">Requirements</option>
              <option value="user_story">User story</option>
              <option value="acceptance_criteria">Acceptance criteria</option>
              <option value="context">Context</option>
            </select>
          </div>
          <div>
            <label className="label">Or upload a file (.txt/.md)</label>
            <input type="file" accept=".txt,.md,.csv,.text" onChange={(e) => setFile(e.target.files?.[0] || null)} />
          </div>
        </div>
        {!file && (
          <div>
            <label className="label">Content</label>
            <textarea
              className="input h-40"
              value={form.content}
              onChange={(e) => setForm({ ...form, content: e.target.value })}
              placeholder={"As a user I want to log in...\nAcceptance criteria:\n- Valid credentials redirect to the dashboard\n- Invalid credentials show an error"}
            />
          </div>
        )}
        <button className="btn btn-primary" onClick={create} disabled={busy || !form.title.trim()}>
          {busy ? "Saving..." : "Save document"}
        </button>
      </div>

      <div className="card p-6">
        <h2 className="text-lg font-semibold mb-4">Documents ({docs.length})</h2>
        <SimpleTable
          heads={["Title", "Type", "Version", "Status", "Actions"]}
          rows={docs.map((d) => [
            <button className="text-left" onClick={() => setViewing(d)}>{d.title}</button>,
            d.doc_type,
            `v${d.version}`,
            <StatusBadge status={d.status} />,
            <div className="flex gap-2 flex-wrap">
              {d.status !== "approved" && (
                <button className="btn btn-sm" onClick={() => approve(d.id)}>Approve</button>
              )}
              <button className="btn btn-sm" onClick={() => newVersion(d)}>New version</button>
              <button className="btn btn-sm" onClick={() => remove(d.id)}>Delete</button>
            </div>,
          ])}
        />
      </div>

      {viewing && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-6 z-50" onClick={() => setViewing(null)}>
          <div className="card p-6 max-w-3xl w-full max-h-[80vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-lg font-semibold">{viewing.title} <span className="badge ml-2">v{viewing.version}</span></h3>
              <button className="btn btn-sm" onClick={() => setViewing(null)}>Close</button>
            </div>
            <pre className="whitespace-pre-wrap text-sm">{viewing.content}</pre>
          </div>
        </div>
      )}
    </div>
  );
}

function Empty() {
  return (
    <div className="card p-8 text-center text-[rgb(var(--text-secondary))]">
      Create a project first, then add requirements here.
    </div>
  );
}
