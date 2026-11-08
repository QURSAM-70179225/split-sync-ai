import { useState } from "react";
import { money } from "../services/format";
import { Avatar, Badge, Card, Spinner } from "./ui";

function PayPalMark() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor" aria-hidden>
      <path d="M7.1 21.3H3.6a.5.5 0 0 1-.5-.6L5.9 3.3c.1-.4.4-.7.8-.7h6.6c2.3 0 4 .5 4.9 1.6.9 1 1.1 2.4.7 4.1-.8 3.8-3.3 5.7-7.3 5.7H9.5a.8.8 0 0 0-.8.7l-.9 5.9a.8.8 0 0 1-.7.7Zm12.5-13c-.9 4.4-3.8 6.6-8.4 6.6h-1l-1.1 6.8a.4.4 0 0 0 .4.5h3c.4 0 .7-.3.7-.6l.6-3.7c.1-.4.4-.6.7-.6h.5c3 0 5.3-1.2 6-4.7.3-1.6.1-3-.7-3.9l-.7-.4Z" />
    </svg>
  );
}

export default function BalancesPanel({ balances, me, onSettle, onNudge }) {
  const [paying, setPaying] = useState(null);
  if (!balances) return null;
  const { debts, members, currency, naive_transfer_count: naive } = balances;
  const saved = Math.max((naive || 0) - debts.length, 0);

  const nameFor = (u) => (me && u.id === me.id ? "You" : u.name);
  const verb = (u) => (me && u.id === me.id ? "owe" : "owes");

  async function settle(d, key) {
    setPaying(key);
    try {
      await onSettle(d);
    } finally {
      setPaying(null);
    }
  }

  const myNet = me ? members.find((m) => m.user.id === me.id)?.net ?? 0 : null;

  return (
    <Card
      data-tour="balances"
      title="Balances & Settlement"
      subtitle="Debts simplified to the fewest payments"
      action={
        myNet !== null && (
          <Badge color={myNet > 0.004 ? "green" : myNet < -0.004 ? "red" : "gray"}>
            {myNet > 0.004 ? `You're owed ${money(myNet, currency)}` : myNet < -0.004 ? `You owe ${money(-myNet, currency)}` : "You're all square"}
          </Badge>
        )
      }
    >
      <div className="grid grid-cols-2 gap-2 px-5 pt-4 sm:grid-cols-3">
        {members.map(({ user, net }) => (
          <div key={user.id} className="flex items-center gap-2.5 rounded-xl border border-gray-800 bg-gray-950/50 px-3 py-2">
            <Avatar user={user} size="sm" />
            <div className="min-w-0">
              <p className="truncate text-xs text-gray-400">{nameFor(user)}</p>
              <p className={`font-mono text-sm font-semibold ${net > 0.004 ? "text-emerald-300" : net < -0.004 ? "text-rose-300" : "text-gray-500"}`}>
                {net > 0.004 ? "+" : ""}
                {money(net, currency)}
              </p>
            </div>
          </div>
        ))}
      </div>

      {saved > 0 && (
        <div data-tour="smart-settlement" className="mx-5 mt-4 flex items-center gap-3 rounded-xl border border-indigo-500/30 bg-indigo-500/10 px-4 py-2.5 text-sm">
          <span className="text-lg">⚡</span>
          <p className="text-indigo-100">
            Smart settlement: <span className="font-semibold">{debts.length} payment{debts.length !== 1 ? "s" : ""}</span> instead of{" "}
            <span className="line-through opacity-60">{naive}</span> — {saved} fewer transfer{saved !== 1 ? "s" : ""}.
          </p>
        </div>
      )}

      <ul className="space-y-2 p-5">
        {debts.length === 0 && (
          <li className="rounded-xl border border-dashed border-gray-800 px-4 py-6 text-center text-sm text-gray-500">🎉 Everyone is settled up.</li>
        )}
        {debts.map((d, idx) => {
          const key = `${d.from_user.id}-${d.to_user.id}-${d.currency}`;
          const mine = me && d.from_user.id === me.id;
          return (
            <li key={key} className={`flex flex-wrap items-center gap-3 rounded-xl border px-4 py-3 ${mine ? "border-indigo-500/40 bg-indigo-500/5" : "border-gray-800 bg-gray-950/40"}`}>
              <div className="flex -space-x-2">
                <Avatar user={d.from_user} />
                <Avatar user={d.to_user} />
              </div>
              <p className="min-w-0 flex-1 text-sm text-gray-300">
                <span className="font-medium text-white">{nameFor(d.from_user)}</span> {verb(d.from_user)}{" "}
                <span className="font-medium text-white">{nameFor(d.to_user)}</span>{" "}
                <span className="font-mono font-semibold text-rose-300">{money(d.amount, d.currency)}</span>
              </p>
              <span data-tour={idx === 0 ? "debt-actions" : undefined} className="flex gap-2">
              <button
                onClick={() => onNudge(d)}
                title="Send an AI-written reminder"
                className="rounded-xl border border-gray-700 px-2.5 py-2 text-xs font-medium text-gray-300 transition hover:bg-gray-800"
              >
                🔔 Nudge
              </button>
              <button
                onClick={() => settle(d, key)}
                disabled={paying !== null}
                className="inline-flex items-center gap-2 rounded-xl bg-[#ffc439] px-3.5 py-2 text-xs font-bold text-[#003087] shadow transition hover:brightness-95 disabled:opacity-60"
              >
                {paying === key ? <Spinner className="h-3.5 w-3.5" /> : <PayPalMark />}
                {paying === key ? "Opening PayPal…" : "Settle via PayPal"}
              </button>
              </span>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
