import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useProjects } from "../lib/project-context";
import { SimpleTable } from "../components/SimpleTable";
import { FieldDefinition, Template, FIELD_TYPES, TEST_PHASES, OUTPUT_DETAILS } from "../lib/types";

const emptyField = (): FieldDefinition => ({
  name: "",
  field_type: "enum",
  description: "",
  sample_values: [],
  required: true,
  unique: false,
});

const blankTemplate = () => ({
  name: "",
  description: "",
  gherkin_template:
    "Scenario: {scenario_title}\n  Given {given}\n  When {when}\n  Then {then}",
  prompt_template: "",
  fields: [] as FieldDefinition[],
  test_phase: "system",
  test_techniques: ["positive", "negative"],
  output_detail: "standard",
});

export default function TemplatesPage() {
  const { current, currentId } = useProjects();
  const [templates, setTemplates] = useState<Template[]>([]);
  const [form, setForm] = useState<any>(blankTemplate());
  const [editingId, setEditingId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    if (!currentId) return;
    setTemplates(await api<Template[]>(`/templates?project_id=${currentId}`));
  }
  useEffect(() => {
    load();
  }, [currentId]);

  async function loadStarter() {
    const starter = await api("/templates/starter");
    setForm({ ...starter });
    setEditingId(null);
  }

  function updateField(i: number, patch: Partial<FieldDefinition>) {
    const fields = [...form.fields];
    fields[i] = { ...fields[i], ...patch };
    setForm({ ...form, fields });
  }
  function removeField(i: number) {
    setForm({ ...form, fields: form.fields.filter((_: any, idx: number) => idx !== i) });
  }

  function edit(t: Template) {
    setForm({ ...t });
    setEditingId(t.id);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function save() {
    if (!form.name.trim()) return;
    setBusy(true);
    try {
      const payload = { ...form, project_id: currentId };
      if (editingId) await api(`/templates/${editingId}`, "PUT", payload);
      else await api("/templates", "POST", payload);
      setForm(blankTemplate());
      setEditingId(null);
      await load();
    } catch (e: any) {
      alert(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    if (!confirm("Delete this template?")) return;
    await api(`/templates/${id}`, "DELETE");
    await load();
  }

  if (!currentId)
    return <div className="card p-8 text-center text-[rgb(var(--text-secondary))]">Create a project first.</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Templates</h1>
          <p className="text-[rgb(var(--text-secondary))]">
            Reusable generation templates with independent field variables and a versioned BDD prompt.
          </p>
        </div>
        <button className="btn" onClick={loadStarter}>Load starter (BDD login)</button>
      </div>

      <div className="card p-6 space-y-4">
        <h2 className="text-lg font-semibold">{editingId ? "Edit template" : "New template"}</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="label">Name</label>
            <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div>
            <label className="label">Description</label>
            <input className="input" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </div>
          <div>
            <label className="label">Test phase</label>
            <select className="input" value={form.test_phase} onChange={(e) => setForm({ ...form, test_phase: e.target.value })}>
              {TEST_PHASES.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Output detail</label>
            <select className="input" value={form.output_detail} onChange={(e) => setForm({ ...form, output_detail: e.target.value })}>
              {OUTPUT_DETAILS.map((p) => <option key={p} value={p}>{p.replace(/_/g, " ")}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Test techniques (comma separated)</label>
            <input
              className="input"
              value={(form.test_techniques || []).join(", ")}
              onChange={(e) => setForm({ ...form, test_techniques: e.target.value.split(",").map((s: string) => s.trim()).filter(Boolean) })}
            />
          </div>
        </div>

        <div>
          <label className="label">Gherkin template (placeholders: {"{field_name}"}, {"{scenario_title}"}, {"{given}"}, {"{when}"}, {"{then}"})</label>
          <textarea className="input h-32 font-mono text-sm" value={form.gherkin_template} onChange={(e) => setForm({ ...form, gherkin_template: e.target.value })} />
        </div>
        <div>
          <label className="label">LLM prompt template (versioned per platform — guides the model)</label>
          <textarea className="input h-24" value={form.prompt_template} onChange={(e) => setForm({ ...form, prompt_template: e.target.value })} placeholder="You are an Enterprise QA engineer. Using the requirements and variable values, write one concrete BDD scenario..." />
        </div>

        {/* Field variables */}
        <div className="border-t border-[rgb(var(--border))] pt-4">
          <div className="flex items-center justify-between mb-2">
            <h3 className="font-semibold">Field variables ({form.fields.length})</h3>
            <button className="btn btn-sm" onClick={() => setForm({ ...form, fields: [...form.fields, emptyField()] })}>+ Add field</button>
          </div>
          <p className="text-xs text-[rgb(var(--text-secondary))] mb-3">
            Each field is generated independently — enums/sampling lists, numbers, dates, booleans, LLM-generated values, or expressions computed from earlier fields.
          </p>
          <div className="space-y-3">
            {form.fields.map((f: FieldDefinition, i: number) => (
              <div key={i} className="border border-[rgb(var(--border))] rounded-xl p-3 space-y-2">
                <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
                  <input className="input" placeholder="name" value={f.name} onChange={(e) => updateField(i, { name: e.target.value })} />
                  <select className="input" value={f.field_type} onChange={(e) => updateField(i, { field_type: e.target.value })}>
                    {FIELD_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                  </select>
                  <input className="input md:col-span-2" placeholder="description" value={f.description} onChange={(e) => updateField(i, { description: e.target.value })} />
                </div>

                {(f.field_type === "enum" || f.field_type === "sampling") && (
                  <input className="input" placeholder="comma separated values e.g. valid, invalid, expired" value={(f.sample_values || []).join(", ")} onChange={(e) => updateField(i, { sample_values: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })} />
                )}
                {f.field_type === "llm_generated" && (
                  <input className="input" placeholder="LLM prompt for this value" value={f.llm_prompt || ""} onChange={(e) => updateField(i, { llm_prompt: e.target.value })} />
                )}
                {f.field_type === "expression" && (
                  <input className="input font-mono text-sm" placeholder="python expr e.g. 'pass' if credential_type=='valid' else 'fail'" value={f.expression || ""} onChange={(e) => updateField(i, { expression: e.target.value })} />
                )}
                {f.field_type === "number" && (
                  <div className="grid grid-cols-3 gap-2">
                    <input className="input" type="number" placeholder="min" value={f.number_min ?? ""} onChange={(e) => updateField(i, { number_min: e.target.value === "" ? undefined : Number(e.target.value) })} />
                    <input className="input" type="number" placeholder="max" value={f.number_max ?? ""} onChange={(e) => updateField(i, { number_max: e.target.value === "" ? undefined : Number(e.target.value) })} />
                    <select className="input" value={f.number_type || "float"} onChange={(e) => updateField(i, { number_type: e.target.value })}>
                      <option value="float">float</option>
                      <option value="int">int</option>
                    </select>
                  </div>
                )}
                {f.field_type === "date" && (
                  <div className="grid grid-cols-2 gap-2">
                    <input className="input" placeholder="date_min ISO (optional)" value={f.date_min || ""} onChange={(e) => updateField(i, { date_min: e.target.value })} />
                    <input className="input" placeholder="date_max ISO (optional)" value={f.date_max || ""} onChange={(e) => updateField(i, { date_max: e.target.value })} />
                  </div>
                )}
                <div className="flex items-center gap-4 text-sm flex-wrap">
                  <label className="flex items-center gap-1"><input type="checkbox" checked={!!f.unique} onChange={(e) => updateField(i, { unique: e.target.checked })} /> unique</label>
                  <label className="flex items-center gap-1"><input type="checkbox" checked={f.required !== false} onChange={(e) => updateField(i, { required: e.target.checked })} /> required</label>
                  <input className="input flex-1 min-w-[180px]" placeholder="depends_on (comma separated field names)" value={(f.depends_on || []).join(", ")} onChange={(e) => updateField(i, { depends_on: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })} />
                  <button className="btn btn-sm" onClick={() => removeField(i)}>Remove</button>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="flex gap-2">
          <button className="btn btn-primary" onClick={save} disabled={busy || !form.name.trim()}>
            {busy ? "Saving..." : editingId ? "Update template" : "Create template"}
          </button>
          {editingId && (
            <button className="btn" onClick={() => { setForm(blankTemplate()); setEditingId(null); }}>Cancel</button>
          )}
        </div>
      </div>

      <div className="card p-6">
        <h2 className="text-lg font-semibold mb-4">Templates ({templates.length})</h2>
        <SimpleTable
          heads={["Name", "Phase", "Fields", "Version", "Actions"]}
          rows={templates.map((t) => [
            <span className="font-medium">{t.name}</span>,
            t.test_phase,
            String(t.fields?.length || 0),
            `v${t.version}`,
            <div className="flex gap-2">
              <button className="btn btn-sm" onClick={() => edit(t)}>Edit</button>
              <button className="btn btn-sm" onClick={() => remove(t.id)}>Delete</button>
            </div>,
          ])}
        />
      </div>
    </div>
  );
}
