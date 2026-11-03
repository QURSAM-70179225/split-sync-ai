import { useState } from "react";
import { money, timeAgo } from "../services/format";
import { Avatar, Badge, Card } from "./ui";

export default function Ledger({ expenses, settlements, onDelete }) {
  const [expanded, setExpanded] = useState(null);

  const items = [
    ...expenses.map((e) => ({ kind: "expense", at: e.created_at, data: e })),
    ...settlements.filter((s) => s.status === "completed").map((s) => ({ kind: "settlement", at: s.completed_at || s.created_at, data: s })),
  ].sort((a, b) => new Date(b.at) - new Date(a.at));

  const total = expenses.reduce((sum, e) => sum + e.amount, 0);
  const currency = expenses[0]?.currency || "USD";

  return (
    <Card title="Activity Ledger" subtitle={`${expenses.length} expenses · ${money(total, currency)} total`}>
      <ul className="scrollbar-thin max-h-[28rem] divide-y divide-gray-800/70 overflow-y-auto">
        {items.length === 0 && <li className="px-5 py-10 text-center text-sm text-gray-500">No activity yet — log your first expense in the chat.</li>}
        {items.map(({ kind, data }) =>
          kind === "settlement" ? (
            <li key={`s${data.id}`} className="flex items-center gap-3 px-5 py-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-500/15 text-sm">✓</div>
              <div className="min-w-0 flex-1">
                <p className="text-sm text-gray-200">
                  <span className="font-medium">{data.from_user.name}</span> paid <span className="font-medium">{data.to_user.name}</span>
                </p>
                <p className="text-xs text-gray-500">Settled via PayPal · {timeAgo(data.completed_at || data.created_at)}</p>
              </div>
              <span className="font-mono text-sm text-emerald-300">{money(data.amount, data.currency)}</span>
            </li>
          ) : (
            <li key={`e${data.id}`} className="group">
              <button onClick={() => setExpanded(expanded === data.id ? null : data.id)} className="flex w-full items-center gap-3 px-5 py-3 text-left hover:bg-gray-900/60">
                <Avatar user={data.payer} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-gray-100">{data.description}</p>
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
