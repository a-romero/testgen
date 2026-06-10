import Link from "next/link";
import { useRouter } from "next/router";
import { LayoutDashboard, FolderKanban, FileText, LayoutTemplate, Sparkles, CheckSquare, FlaskConical } from "lucide-react";
import { useProjects } from "../lib/project-context";

const NavItem = ({ href, icon: Icon, label }: any) => {
  const router = useRouter();
  const active = href === "/" ? router.pathname === "/" : router.pathname.startsWith(href);
  return (
    <Link
      href={href}
      className={`flex items-center gap-3 px-3 py-2 rounded-xl transition-colors duration-200 ${
        active ? "bg-[rgb(var(--accent))] text-white" : "text-[rgb(var(--text))] hover:bg-[rgb(var(--hover))]"
      }`}
    >
      <Icon size={18} />
      <span className="font-medium">{label}</span>
    </Link>
  );
};

function ProjectSwitcher() {
  const { projects, currentId, setCurrentId } = useProjects();
  if (!projects.length) {
    return <span className="text-sm text-[rgb(var(--text-secondary))]">No projects yet</span>;
  }
  return (
    <div className="flex items-center gap-2">
      <span className="label">Project</span>
      <select
        className="input w-64"
        value={currentId}
        onChange={(e) => setCurrentId(e.target.value)}
      >
        {projects.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name}
            {p.market || p.platform ? ` — ${[p.market, p.platform].filter(Boolean).join("/")}` : ""}
          </option>
        ))}
      </select>
    </div>
  );
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="h-screen flex overflow-hidden">
      <aside className="w-64 border-r border-[rgb(var(--border))] bg-[rgb(var(--card))] p-4 flex flex-col gap-4 overflow-y-auto">
        <div className="flex items-center gap-3 px-2">
          <div className="w-11 h-11 rounded-xl bg-[rgb(var(--accent))] flex items-center justify-center">
            <FlaskConical size={22} className="text-white" />
          </div>
          <div>
            <div className="font-semibold leading-6 text-xl text-[rgb(var(--text))]">TestGen</div>
            <div className="text-xs text-[rgb(var(--text-secondary))] -mt-1">QA Test Case Studio</div>
          </div>
        </div>
        <nav className="flex flex-col gap-1">
          <NavItem href="/" icon={LayoutDashboard} label="Dashboard" />
          <div className="text-xs uppercase text-[rgb(var(--text-secondary))] px-3 pt-3">Build</div>
          <NavItem href="/projects" icon={FolderKanban} label="Projects" />
          <NavItem href="/documents" icon={FileText} label="Requirements" />
          <NavItem href="/templates" icon={LayoutTemplate} label="Templates" />
          <NavItem href="/generate" icon={Sparkles} label="Generate" />
          <NavItem href="/testcases" icon={CheckSquare} label="Review & Approve" />
        </nav>
        <div className="mt-auto">
          <div className="card p-3">
            <div className="text-sm font-medium text-[rgb(var(--text))]">Enterprise QA</div>
            <div className="text-xs text-[rgb(var(--text-secondary))]">BDD test case generation</div>
          </div>
        </div>
      </aside>

      <section className="flex-1 flex flex-col overflow-hidden">
        <div className="border-b border-[rgb(var(--border))] bg-[rgb(var(--card))]/70 backdrop-blur flex-shrink-0">
          <div className="container py-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="badge">v0.1</span>
            </div>
            <ProjectSwitcher />
          </div>
        </div>
        <main className="container py-6 overflow-y-auto flex-1">{children}</main>
      </section>
    </div>
  );
}
