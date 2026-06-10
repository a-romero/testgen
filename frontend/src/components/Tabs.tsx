import { useState } from "react";

export function Tabs({ tabs }: { tabs: { key: string; label: string; content: React.ReactNode }[] }) {
  const [active, setActive] = useState(tabs[0]?.key);
  return (
    <div>
      <div className="flex gap-2 mb-3 flex-wrap">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setActive(t.key)}
            className={`px-3 py-2 rounded-xl transition-colors duration-200 ${
              active === t.key
                ? "bg-[rgb(var(--accent))] text-white"
                : "text-[rgb(var(--text))] hover:bg-[rgb(var(--hover))] border border-[rgb(var(--border))]"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div>{tabs.find((t) => t.key === active)?.content}</div>
    </div>
  );
}
