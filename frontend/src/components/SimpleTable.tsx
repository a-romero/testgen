export function SimpleTable({
  heads,
  rows,
}: {
  heads: string[];
  rows: (string | React.ReactNode)[][];
}) {
  return (
    <div className="overflow-auto">
      <table className="min-w-full text-sm">
        <thead className="bg-[rgb(var(--card))]">
          <tr>
            {heads.map((h, i) => (
              <th
                key={i}
                className="px-3 py-2 text-left font-medium text-[rgb(var(--text-secondary))] border-b border-[rgb(var(--border))]"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr
              key={i}
              className="border-t border-[rgb(var(--border))] hover:bg-[rgb(var(--hover))] transition-colors duration-200"
            >
              {r.map((c, j) => (
                <td key={j} className="px-3 py-2 text-[rgb(var(--text))] align-top">
                  {c}
                </td>
              ))}
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td
                colSpan={heads.length}
                className="px-3 py-6 text-center text-[rgb(var(--text-secondary))]"
              >
                No records yet.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    approved: "bg-green-900/40 text-green-300 border-green-700",
    rejected: "bg-red-900/40 text-red-300 border-red-700",
    needs_changes: "bg-yellow-900/40 text-yellow-300 border-yellow-700",
    pending_review: "bg-blue-900/40 text-blue-300 border-blue-700",
    pending_approval: "bg-blue-900/40 text-blue-300 border-blue-700",
    generated: "bg-[rgb(var(--input-bg))] text-[rgb(var(--text-secondary))] border-[rgb(var(--border))]",
    draft: "bg-[rgb(var(--input-bg))] text-[rgb(var(--text-secondary))] border-[rgb(var(--border))]",
  };
  const cls = map[status] || "bg-[rgb(var(--input-bg))] text-[rgb(var(--text))] border-[rgb(var(--border))]";
  return (
    <span className={`inline-flex items-center px-2 py-1 rounded-lg text-xs border ${cls}`}>
      {status.replace(/_/g, " ")}
    </span>
  );
}
