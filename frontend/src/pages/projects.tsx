import { useState } from "react";
import { api } from "../lib/api";
import { useProjects } from "../lib/project-context";
import { SimpleTable } from "../components/SimpleTable";
import { Project } from "../lib/types";

export default function ProjectsPage() {
  const { projects, reload, setCurrentId } = useProjects();
  const [form, setForm] = useState({ name: "", description: "", market: "", platform: "" });
  const [busy, setBusy] = useState(false);

  async function create() {
    if (!form.name.trim()) return;
    setBusy(true);
    try {
      const p = await api<Project>("/projects", "POST", form);
      setForm({ name: "", description: "", market: "", platform: "" });
      await reload();
      setCurrentId(p.id);
    } catch (e: any) {
      alert(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    if (!confirm("Delete this project and all its documents, templates and test cases?")) return;
    await api(`/projects/${id}`, "DELETE");
    await reload();
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Projects</h1>
        <p className="text-[rgb(var(--text-secondary))]">
          Test cases are generated and tracked per project, scoped by market and platform.
        </p>
      </div>

      <div className="card p-6 space-y-4">
        <h2 className="text-lg font-semibold">New project</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="label">Name</label>
            <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. Checkout Revamp" />
          </div>
          <div>
            <label className="label">Description</label>
            <input className="input" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </div>
          <div>
            <label className="label">Market</label>
            <input className="input" value={form.market} onChange={(e) => setForm({ ...form, market: e.target.value })} placeholder="e.g. UK" />
          </div>
          <div>
            <label className="label">Platform</label>
            <input className="input" value={form.platform} onChange={(e) => setForm({ ...form, platform: e.target.value })} placeholder="e.g. Web / iOS / Android" />
          </div>
        </div>
        <button className="btn btn-primary" onClick={create} disabled={busy || !form.name.trim()}>
          {busy ? "Creating..." : "Create project"}
        </button>
      </div>

      <div className="card p-6">
        <h2 className="text-lg font-semibold mb-4">All projects ({projects.length})</h2>
        <SimpleTable
          heads={["Name", "Market", "Platform", "Description", ""]}
          rows={projects.map((p) => [
            <span className="font-medium">{p.name}</span>,
            p.market || "—",
            p.platform || "—",
            p.description || "—",
            <button className="btn btn-sm" onClick={() => remove(p.id)}>Delete</button>,
          ])}
        />
      </div>
    </div>
  );
}
