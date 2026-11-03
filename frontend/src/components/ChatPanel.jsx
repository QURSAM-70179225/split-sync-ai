import { useEffect, useRef, useState } from "react";
import { money } from "../services/format";
import { Badge, Card, Spinner } from "./ui";

const EXAMPLES = [
  "I paid $60 for dinner, split between me, Alex, and Sarah",
  "Alex covered the $24 Uber, split with me",
  "Sarah paid 90 for groceries for everyone",
  "I paid $100 for concert tickets: Alex owes 60, I owe 40",
];

export default function ChatPanel({ group, me, onExpenseAdded, parseExpense }) {
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const scroller = useRef(null);

  useEffect(() => setMessages([]), [group?.id]);
  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }, [messages, busy]);

  async function send(e) {
    e?.preventDefault();
    const value = text.trim();
    if (!value || busy) return;
    setText("");
    setMessages((m) => [...m, { role: "user", text: value, author: me }]);
    setBusy(true);
    try {
      const res = await parseExpense(value);
      setMessages((m) => [...m, { role: "ai", result: res }]);
      onExpenseAdded?.(res);
    } catch (err) {
      setMessages((m) => [...m, { role: "error", text: err.message }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card
      title="Expense Assistant"
      subtitle={me ? `Chatting as ${me.name} — "I" and "me" mean you` : "Describe an expense in plain English"}
      action={<Badge color="indigo">✨ AI</Badge>}
      className="h-full"
    >
      <div ref={scroller} className="scrollbar-thin flex-1 space-y-3 overflow-y-auto px-5 py-4">
        {messages.length === 0 && (
          <div className="py-6 text-center">
            <p className="text-3xl">🧾</p>
            <p className="mt-2 text-sm font-medium text-gray-300">Just tell me what happened</p>
            <p className="mb-4 text-xs text-gray-500">I'll figure out who paid, how much, and who owes what.</p>
            <div className="flex flex-col gap-2">
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  onClick={() => setText(ex)}
                  className="rounded-xl border border-gray-800 bg-gray-950/60 px-3 py-2 text-left text-xs text-gray-400 transition hover:border-indigo-500/40 hover:text-gray-200"
                >
                  “{ex}”
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => {
          if (m.role === "user")
            return (
              <div key={i} className="animate-fade-up flex justify-end">
                <div className="max-w-[85%] rounded-2xl rounded-br-md bg-indigo-600 px-4 py-2.5 text-sm text-white shadow-lg shadow-indigo-900/30">
                  {m.text}
                </div>
              </div>
            );
          if (m.role === "error")
            return (
              <div key={i} className="animate-fade-up max-w-[85%] rounded-2xl rounded-bl-md border border-rose-500/30 bg-rose-500/10 px-4 py-2.5 text-sm text-rose-200">
                Hmm, I couldn't log that: {m.text}
              </div>
            );
          const { expense, parsed, new_members } = m.result;
          return (
            <div key={i} className="animate-fade-up max-w-[90%] rounded-2xl rounded-bl-md border border-gray-800 bg-gray-950/80 p-4 text-sm">
              <p className="text-gray-300">
                Logged <span className="font-semibold text-white">{expense.description}</span> —{" "}
                <span className="font-semibold text-emerald-300">{money(expense.amount, expense.currency)}</span> paid by{" "}
                <span className="font-medium text-white">{expense.payer.name}</span>.
              </p>
              <div className="mt-3 space-y-1.5 rounded-xl bg-gray-900 p-3">
                {expense.splits.map((s) => (
                  <div key={s.id} className="flex items-center justify-between text-xs">
                    <span className="text-gray-400">{s.user.name}</span>
                    <span className="font-mono text-gray-200">{money(s.owed_amount, expense.currency)}</span>
                  </div>
                ))}
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                <Badge color="indigo">{parsed.split_type === "equal" ? "Split equally" : "Custom split"}</Badge>
                {new_members.map((u) => (
                  <Badge key={u.id} color="amber">+ added {u.name}</Badge>
                ))}
              </div>
            </div>
          );
        })}

        {busy && (
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <Spinner className="h-3.5 w-3.5" /> Parsing with AI…
          </div>
        )}
      </div>

      <form onSubmit={send} className="border-t border-gray-800 p-3">
        <div className="flex items-end gap-2 rounded-2xl border border-gray-700 bg-gray-950 p-2 focus-within:border-indigo-500 focus-within:ring-2 focus-within:ring-indigo-500/20">
          <textarea
            rows={1}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) send(e);
            }}
            placeholder={group ? "e.g. I paid $45 for pizza, split with Alex" : "Create a group first"}
            disabled={!group}
            className="max-h-32 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm text-gray-100 placeholder-gray-500 outline-none"
          />
          <button
            disabled={!text.trim() || busy || !group}
            className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-600 text-white transition hover:bg-indigo-500 disabled:opacity-40"
            aria-label="Send"
          >
            {busy ? <Spinner /> : "↑"}
          </button>
        </div>
      </form>
    </Card>
  );
}
