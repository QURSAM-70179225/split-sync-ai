import { useEffect, useState } from "react";
import { api } from "../services/api";
import { cat } from "../services/categories";
import { money } from "../services/format";
import { Avatar, Card, Spinner } from "./ui";

const SUGGESTIONS = ["How much did we spend on food?", "Who owes me?", "Who paid the most?", "What was our largest expense?"];

function Stat({ label, value, hint, tone = "text-white" }) {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-950/50 px-4 py-3">
      <p className="text-[11px] font-medium tracking-wider text-gray-500 uppercase">{label}</p>
      <p className={`mt-1 font-mono text-xl font-semibold ${tone}`}>{value}</p>
      {hint && <p className="mt-0.5 text-[11px] text-gray-500">{hint}</p>}
    </div>
  );
}

function Copilot({ groupId, me }) {
  const [q, setQ] = useState("");
  const [thread, setThread] = useState([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => setThread([]), [groupId]);

  async function ask(question) {
    const text = (question ?? q).trim();
    if (!text || busy) return;
    setQ("");
    setBusy(true);
    setThread((t) => [...t, { role: "q", text }]);
    try {
      const res = await api.ask(groupId, text, me?.id);
      setThread((t) => [...t, { role: "a", text: res.answer }]);
    } catch (e) {
      setThread((t) => [...t, { role: "a", text: `⚠️ ${e.message}` }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-xl border border-indigo-500/30 bg-gradient-to-br from-indigo-500/10 to-violet-500/5 p-4">
      <p className="text-sm font-semibold text-indigo-200">✨ Ask your ledger</p>
      <p className="mb-3 text-xs text-gray-400">Ask anything about this group's money in plain English.</p>
      {thread.length > 0 && (
        <div className="scrollbar-thin mb-3 max-h-56 space-y-2 overflow-y-auto">
          {thread.map((m, i) => (
            <p
              key={i}
              className={`animate-fade-up rounded-xl px-3 py-2 text-sm ${m.role === "q" ? "ml-8 bg-indigo-600 text-white" : "mr-8 bg-gray-900 text-gray-200"}`}
            >
              {m.text}
            </p>
          ))}
        </div>
      )}
      <div className="mb-2 flex flex-wrap gap-1.5">
        {SUGGESTIONS.map((s) => (
          <button key={s} onClick={() => ask(s)} className="rounded-full border border-gray-700 px-2.5 py-1 text-[11px] text-gray-400 hover:border-indigo-500/50 hover:text-gray-200">
            {s}
          </button>
        ))}
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          ask();
        }}
        className="flex gap-2"
      >
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="e.g. How much has Alex spent on transport?"
          className="flex-1 rounded-xl border border-gray-700 bg-gray-950 px-3 py-2 text-sm outline-none focus:border-indigo-500"
        />
        <button disabled={busy || !q.trim()} className="rounded-xl bg-indigo-600 px-3 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-40">
          {busy ? <Spinner /> : "Ask"}
        </button>
      </form>
    </div>
  );
}

export default function InsightsPanel({ groupId, me, refreshKey }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    api
      .insights(groupId)
      .then((d) => alive && (setData(d), setError("")))
      .catch((e) => alive && setError(e.message));
    return () => {
      alive = false;
    };
  }, [groupId, refreshKey]);

  if (error) return <Card title="Insights"><p className="p-5 text-sm text-rose-300">{error}</p></Card>;
  if (!data) return <Card title="Insights"><div className="flex justify-center p-10 text-gray-500"><Spinner className="h-5 w-5" /></div></Card>;

  const cur = data.currency;
  const maxCat = Math.max(...data.by_category.map((c) => c.total), 1);
  const maxPerson = Math.max(...data.by_person.flatMap((p) => [p.paid, p.share]), 1);
  const maxDay = Math.max(...data.daily.map((d) => d.total), 1);
  const settledPct = data.settled_amount + data.outstanding_amount > 0
    ? Math.round((data.settled_amount / (data.settled_amount + data.outstanding_amount)) * 100) : 100;

  return (
    <Card title="Insights" subtitle="Where the money went — updated live">
      <div className="space-y-5 p-5">
        <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
          <Stat label="Total spent" value={money(data.total_spent, cur)} hint={`${data.expense_count} expenses`} />
          <Stat label="Avg expense" value={money(data.avg_expense, cur)} />
          <Stat label="Settled" value={`${settledPct}%`} hint={`${money(data.settled_amount, cur)} via PayPal`} tone="text-emerald-300" />
          <Stat label="Payments saved" value={data.payments_saved} hint="by smart settlement" tone="text-indigo-300" />
        </div>

        {data.highlights.length > 0 && (
          <ul className="space-y-1.5">
            {data.highlights.map((h) => (
              <li key={h} className="flex gap-2 rounded-lg bg-gray-950/40 px-3 py-2 text-sm text-gray-300">
                <span>💡</span>
                {h}
              </li>
            ))}
          </ul>
        )}

        <Copilot groupId={groupId} me={me} />

        {data.by_category.length > 0 && (
          <section>
            <h3 className="mb-2 text-xs font-semibold tracking-wider text-gray-500 uppercase">By category</h3>
            <div className="space-y-2">
              {data.by_category.map((c) => {
                const meta = cat(c.category);
                return (
                  <div key={c.category} className="flex items-center gap-3 text-sm">
                    <span className="w-32 shrink-0 truncate text-gray-300">{meta.icon} {meta.label}</span>
                    <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-gray-800">
                      <div className={`h-full rounded-full ${meta.color}`} style={{ width: `${(c.total / maxCat) * 100}%` }} />
                    </div>
                    <span className="w-24 text-right font-mono text-xs text-gray-200">{money(c.total, cur)}</span>
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {data.by_person.length > 0 && (
          <section>
            <h3 className="mb-1 text-xs font-semibold tracking-wider text-gray-500 uppercase">Paid vs. fair share</h3>
            <p className="mb-2 flex gap-3 text-[11px] text-gray-500">
              <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-indigo-500" /> Paid</span>
              <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-gray-500" /> Fair share</span>
            </p>
            <div className="space-y-2.5">
              {data.by_person.map((p) => (
                <div key={p.user.id} className="flex items-center gap-3">
                  <Avatar user={p.user} size="sm" />
                  <span className="w-16 shrink-0 truncate text-sm text-gray-300">{p.user.name}</span>
                  <div className="flex-1 space-y-1">
                    <div className="h-2 rounded-full bg-indigo-500" style={{ width: `${Math.max((p.paid / maxPerson) * 100, 1)}%` }} />
                    <div className="h-2 rounded-full bg-gray-600" style={{ width: `${Math.max((p.share / maxPerson) * 100, 1)}%` }} />
                  </div>
                  <span className="w-28 text-right font-mono text-[11px] text-gray-400">
                    {money(p.paid, cur)}
                    <br />
                    <span className="text-gray-600">{money(p.share, cur)}</span>
                  </span>
                </div>
              ))}
            </div>
          </section>
        )}

        {data.daily.length > 1 && (
          <section>
            <h3 className="mb-2 text-xs font-semibold tracking-wider text-gray-500 uppercase">Daily spend</h3>
            <div className="flex h-28 items-end gap-1.5">
              {data.daily.map((d) => (
                <div key={d.date} className="group flex flex-1 flex-col items-center gap-1">
                  <span className="font-mono text-[10px] text-gray-500 opacity-0 transition group-hover:opacity-100">{money(d.total, cur)}</span>
                  <div className="w-full rounded-t-md bg-gradient-to-t from-indigo-600 to-violet-500" style={{ height: `${(d.total / maxDay) * 80}px` }} />
                  <span className="text-[10px] text-gray-500">{new Date(d.date + "T00:00").toLocaleDateString(undefined, { weekday: "short" })}</span>
                </div>
              ))}
            </div>
          </section>
        )}
      </div>
    </Card>
  );
}
