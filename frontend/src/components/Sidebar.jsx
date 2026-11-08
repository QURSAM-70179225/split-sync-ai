import { Avatar, Badge } from "./ui";

export default function Sidebar({ groups, activeId, onSelect, onCreate, onSeed, seeding, health, open, onClose }) {
  return (
    <>
      {open && <div className="fixed inset-0 z-30 bg-black/60 lg:hidden" onClick={onClose} />}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-72 flex-col border-r border-gray-800 bg-gray-950 transition-transform lg:static lg:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center gap-3 px-5 py-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 text-lg shadow-lg shadow-indigo-900/50">
            💸
          </div>
          <div>
            <p className="font-semibold tracking-tight">SplitSync AI</p>
            <p className="text-[11px] text-gray-500">Talk. Split. Settle.</p>
          </div>
        </div>

        <div className="flex items-center justify-between px-5 pt-2 pb-2">
          <p className="text-[11px] font-semibold tracking-wider text-gray-500 uppercase">Groups</p>
          <button
            onClick={onCreate}
            className="rounded-lg px-2 py-1 text-xs font-medium text-indigo-300 hover:bg-indigo-500/10"
          >
            + New
          </button>
        </div>

        <nav data-tour="groups" className="scrollbar-thin flex-1 space-y-1 overflow-y-auto px-3">
          {groups.length === 0 && (
            <p className="px-2 py-6 text-center text-sm text-gray-500">No groups yet. Create one to get started.</p>
          )}
          {groups.map((g) => (
            <button
              key={g.id}
              onClick={() => onSelect(g.id)}
              className={`group flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition ${
                g.id === activeId ? "bg-indigo-500/10 ring-1 ring-indigo-500/30" : "hover:bg-gray-900"
              }`}
            >
              <div className="min-w-0 flex-1">
                <p className={`truncate text-sm font-medium ${g.id === activeId ? "text-indigo-200" : "text-gray-200"}`}>
                  {g.name}
                </p>
                <p className="text-xs text-gray-500">{g.members.length} members</p>
              </div>
              <div className="flex -space-x-2">
                {g.members.slice(0, 3).map((m) => (
                  <Avatar key={m.id} user={m} size="sm" />
                ))}
              </div>
            </button>
          ))}
        </nav>

        <div className="px-3 pb-3">
          <button
            onClick={onSeed}
            disabled={seeding}
            className="w-full rounded-xl border border-dashed border-gray-700 px-3 py-2 text-xs text-gray-400 transition hover:border-indigo-500/50 hover:text-gray-200 disabled:opacity-50"
          >
            🌴 {seeding ? "Loading…" : "Load demo trip"}
          </button>
        </div>

        <div data-tour="status" className="space-y-2 border-t border-gray-800 px-5 py-4 text-xs">
          <div className="flex items-center justify-between">
            <span className="text-gray-500">AI parser</span>
            {health ? (
              <Badge color={health.ai_mode === "offline" ? "amber" : "green"}>
                {health.ai_mode === "offline" ? "Offline fallback" : health.ai_mode.replace("gemini:", "Gemini · ")}
              </Badge>
            ) : (
              <Badge color="red">API offline</Badge>
            )}
          </div>
          <div className="flex items-center justify-between">
            <span className="text-gray-500">PayPal</span>
            {!health ? (
              <Badge color="red">—</Badge>
            ) : health.paypal_mode === "sandbox" ? (
              <Badge color="green">Sandbox</Badge>
            ) : (
              <Badge color="amber">Demo checkout</Badge>
            )}
          </div>
        </div>
      </aside>
    </>
  );
}
