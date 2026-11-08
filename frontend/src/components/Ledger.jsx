import { useMemo, useState } from "react";
import { api } from "../services/api";
import { CATEGORIES, cat } from "../services/categories";
import { money, timeAgo } from "../services/format";
import { Avatar, Badge, Card } from "./ui";

const SOURCE_BADGE = { voice: "🎙️ voice", receipt: "📷 receipt", demo: null, chat: null };

export default function Ledger({ groupId, expenses, settlements, onDelete }) {
  const [expanded, setExpanded] = useState(null);
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");

  const usedCats = useMemo(() => [...new Set(expenses.map((e) => e.category || "other"))], [expenses]);

  const items = useMemo(() => {
    const q = query.trim().toLowerCase();
    const matches = (e) =>
      (filter === "all" || (e.category || "other") === filter) &&
      (!q || e.description.toLowerCase().includes(q) || e.payer.name.toLowerCase().includes(q) || e.raw_text.toLowerCase().includes(q));
    return [
      ...expenses.filter(matches).map((e) => ({ kind: "expense", at: e.created_at, data: e })),
      ...(filter === "all" && !q
        ? settlements.filter((s) => s.status === "completed").map((s) => ({ kind: "settlement", at: s.completed_at || s.created_at, data: s }))
        : []),
    ].sort((a, b) => new Date(b.at) - new Date(a.at));
  }, [expenses, settlements, filter, query]);

  const total = expenses.reduce((sum, e) => sum + e.amount, 0);
  const currency = expenses[0]?.currency || "USD";

  return (
    <Card
      title="Activity Ledger"
      subtitle={`${expenses.length} expenses · ${money(total, currency)} total`}
      action={
        expenses.length > 0 && (
          <a href={api.exportCsvUrl(groupId)} className="rounded-lg border border-gray-700 px-2.5 py-1 text-xs text-gray-300 hover:bg-gray-800" download>
            ⬇ Export CSV
          </a>
        )
      }
    >
      {expenses.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 border-b border-gray-800 px-5 py-3">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search…"
            className="w-36 rounded-lg border border-gray-700 bg-gray-950 px-2.5 py-1 text-xs outline-none focus:border-indigo-500"
          />
          {["all", ...usedCats].map((c) => (
            <button
              key={c}
              onClick={() => setFilter(c)}
              className={`rounded-full px-2.5 py-1 text-[11px] transition ${filter === c ? "bg-indigo-500/20 text-indigo-200 ring-1 ring-indigo-500/40" : "text-gray-400 hover:bg-gray-800"}`}
            >
              {c === "all" ? "All" : `${CATEGORIES[c]?.icon ?? "🧾"} ${CATEGORIES[c]?.label ?? c}`}
            </button>
          ))}
        </div>
      )}
      <ul className="scrollbar-thin max-h-[30rem] divide-y divide-gray-800/70 overflow-y-auto">
        {items.length === 0 && (
          <li className="px-5 py-10 text-center text-sm text-gray-500">
            {expenses.length ? "Nothing matches that filter." : "No activity yet — log your first expense in the chat."}
          </li>
        )}
        {items.map(({ kind, data }) =>
          kind === "settlement" ? (
            <li key={`s${data.id}`} className="flex items-center gap-3 px-5 py-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-500/15 text-sm">✓</div>
              <div className="min-w-0 flex-1">
                <p className="text-sm text-gray-200">
                  <span className="font-medium">{data.from_user.name}</span> paid <span className="font-medium">{data.to_user.name}</span>
                </p>
                <p className="text-xs text-gray-500">
                  Settled via PayPal{data.paypal_order_id?.startsWith("DEMO-") ? " (demo)" : ""} · {timeAgo(data.completed_at || data.created_at)}
                </p>
              </div>
              <span className="font-mono text-sm text-emerald-300">{money(data.amount, data.currency)}</span>
            </li>
          ) : (
            <li key={`e${data.id}`}>
              <button onClick={() => setExpanded(expanded === data.id ? null : data.id)} className="flex w-full items-center gap-3 px-5 py-3 text-left hover:bg-gray-900/60">
                <span className="relative">
                  <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gray-800 text-base">{cat(data.category).icon}</span>
                  <span className="absolute -right-1 -bottom-1"><Avatar user={data.payer} size="xs" /></span>
                </span>
                <div className="min-w-0 flex-1">
                  <p className="flex items-center gap-2 truncate text-sm font-medium text-gray-100">
                    {data.description}
                    {SOURCE_BADGE[data.source] && <Badge>{SOURCE_BADGE[data.source]}</Badge>}
                  </p>
                  <p className="text-xs text-gray-500">
                    {data.payer.name} paid · split {data.splits.length} ways · {timeAgo(data.created_at)}
                  </p>
                </div>
                <div className="text-right">
                  <p className="font-mono text-sm font-semibold text-gray-100">{money(data.amount, data.currency)}</p>
                  {data.splits.every((s) => s.status === "paid") && data.splits.length > 1 && <Badge color="green">settled</Badge>}
                </div>
              </button>
              {expanded === data.id && (
                <div className="animate-fade-up mx-5 mb-3 rounded-xl border border-gray-800 bg-gray-950/70 p-3">
                  <p className="mb-2 text-xs text-gray-500 italic">“{data.raw_text}”</p>
                  {data.items?.length > 0 && (
                    <div className="mb-2 space-y-0.5 border-b border-gray-800 pb-2">
                      {data.items.map((it, i) => (
                        <div key={i} className="flex justify-between text-[11px] text-gray-400">
                          <span>{it.name}{it.assigned_to?.length ? ` · ${it.assigned_to.join(", ")}` : ""}</span>
                          <span className="font-mono">{money(it.price, data.currency)}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  <div className="space-y-1.5">
                    {data.splits.map((s) => (
                      <div key={s.id} className="flex items-center justify-between text-xs">
                        <span className="flex items-center gap-2 text-gray-300">
                          <Avatar user={s.user} size="sm" /> {s.user.name}
                          {s.user.id === data.payer.id && <span className="text-gray-600">(payer)</span>}
                        </span>
                        <span className="flex items-center gap-2">
                          <span className="font-mono text-gray-200">{money(s.owed_amount, data.currency)}</span>
                          {s.user.id !== data.payer.id && <Badge color={s.status === "paid" ? "green" : "amber"}>{s.status}</Badge>}
                        </span>
                      </div>
                    ))}
                  </div>
                  <div className="mt-3 flex justify-end">
                    <button onClick={() => onDelete(data.id)} className="text-xs text-gray-500 hover:text-rose-400">Delete expense</button>
                  </div>
                </div>
              )}
            </li>
          )
        )}
      </ul>
    </Card>
  );
}
