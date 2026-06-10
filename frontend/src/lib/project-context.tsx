import React, { createContext, useContext, useEffect, useState } from "react";
import { api } from "./api";
import { Project } from "./types";

interface Ctx {
  projects: Project[];
  current?: Project;
  currentId: string;
  setCurrentId: (id: string) => void;
  reload: () => Promise<void>;
}

const ProjectContext = createContext<Ctx>({
  projects: [],
  currentId: "",
  setCurrentId: () => {},
  reload: async () => {},
});

export function ProjectProvider({ children }: { children: React.ReactNode }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [currentId, setCurrentIdState] = useState<string>("");

  async function reload() {
    try {
      const res = await api<Project[]>("/projects");
      setProjects(res);
      setCurrentIdState((prev) => {
        if (prev && res.some((p) => p.id === prev)) return prev;
        const stored = typeof window !== "undefined" ? localStorage.getItem("testgen.project") : "";
        if (stored && res.some((p) => p.id === stored)) return stored;
        return res[0]?.id || "";
      });
    } catch (e) {
      console.error("Failed to load projects", e);
    }
  }

  useEffect(() => {
    reload();
  }, []);

  function setCurrentId(id: string) {
    setCurrentIdState(id);
    if (typeof window !== "undefined") localStorage.setItem("testgen.project", id);
  }

  const current = projects.find((p) => p.id === currentId);
  return (
    <ProjectContext.Provider value={{ projects, current, currentId, setCurrentId, reload }}>
      {children}
    </ProjectContext.Provider>
  );
}

export const useProjects = () => useContext(ProjectContext);
