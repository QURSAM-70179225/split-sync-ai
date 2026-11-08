import { useEffect, useRef, useState } from "react";
import { useSpeech } from "../hooks/useSpeech";
import { cat } from "../services/categories";
import { money } from "../services/format";
import { Badge, Card, Spinner } from "./ui";

const EXAMPLES = [
  "I paid $60 for dinner, split between me, Alex, and Sarah",
  "Alex covered the $24 Uber, split with me",
  "Sarah paid 90 for groceries for everyone",
  "I paid $100 for concert tickets: Alex owes 60, I owe 40",
];

function ExpenseCard({ result }) {
  const { expense, parsed, new_members, notes, ai_mode } = result;
  const c = cat(expense.category);
  return (
    <div className="animate-fade-up max-w-[92%] rounded-2xl rounded-bl-md border border-gray-800 bg-gray-950/80 p-4 text-sm">
      <div className="flex items-start gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gray-900 text-lg">{c.icon}</span>
        <p className="text-gray-300">
          Logged <span className="font-semibold text-white">{expense.description}</span> —{" "}
          <span className="font-semibold text-emerald-300">{money(expense.amount, expense.currency)}</span> paid by{" "}
          <span className="font-medium text-white">{expense.payer.name}</span>.
        </p>
      </div>
      {expense.items?.length > 0 && (
        <div className="mt-3 space-y-1 rounded-xl border border-gray-800 p-3">
          <p className="mb-1 text-[11px] font-semibold tracking-wider text-gray-500 uppercase">Receipt items</p>
          {expense.items.map((it, i) => (
            <div key={i} className="flex justify-between gap-2 text-xs">
              <span className="truncate text-gray-400">
                {it.name}
                {it.assigned_to?.length > 0 && <span className="text-indigo-300"> · {it.assigned_to.join(", ")}</span>}
              </span>
              <span className="font-mono text-gray-300">{money(it.price, expense.currency)}</span>
            </div>
          ))}
        </div>
      )}
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
        <Badge>{c.label}</Badge>
        {ai_mode !== "offline" && <Badge color="green">✨ Gemini</Badge>}
        {new_members.map((u) => (
          <Badge key={u.id} color="amber">+ added {u.name}</Badge>
        ))}
      </div>
      {notes?.map((n) => (
        <p key={n} className="mt-2 text-[11px] text-amber-300/80">ℹ️ {n}</p>
      ))}
    </div>
  );
}

export default function ChatPanel({ group, me, parseExpense, scanReceipt }) {
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const scroller = useRef(null);
  const fileInput = useRef(null);

  const speech = useSpeech({ onFinal: (t) => t && send(null, t, "voice") });

  useEffect(() => setMessages([]), [group?.id]);
  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }, [messages, busy]);

  async function run(userMsg, task) {
    setMessages((m) => [...m, userMsg]);
    setBusy(true);
    try {
      const res = await task();
      setMessages((m) => [...m, { role: "ai", result: res }]);
    } catch (err) {
      setMessages((m) => [...m, { role: "error", text: err.message }]);
    } finally {
      setBusy(false);
    }
  }

  function send(e, override, source = "chat") {
    e?.preventDefault();
    const value = (override ?? text).trim();
    if (!value || busy || !group) return;
    if (!override) setText("");
    run({ role: "user", text: value, source }, () => parseExpense(value, source));
  }

  function onReceipt(e) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file || busy) return;
    const note = text.trim();
    setText("");
    run({ role: "user", text: note, image: URL.createObjectURL(file), source: "receipt" }, () => scanReceipt(file, note));
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
          <div className="py-4 text-center">
            <p className="text-3xl">🧾</p>
            <p className="mt-2 text-sm font-medium text-gray-300">Type it, say it, or snap the receipt</p>
            <p className="mb-4 text-xs text-gray-500">I'll work out who paid, how much, and who owes what.</p>
            <div className="mb-4 flex justify-center gap-2 text-[11px]">
              <Badge>⌨️ Natural language</Badge>
              <Badge>🎙️ Voice</Badge>
              <Badge>📷 Receipt scan</Badge>
            </div>
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
                <div className="max-w-[85%] space-y-2 rounded-2xl rounded-br-md bg-indigo-600 px-4 py-2.5 text-sm text-white shadow-lg shadow-indigo-900/30">
                  {m.image && <img src={m.image} alt="Receipt" className="max-h-48 rounded-lg object-cover" />}
                  {m.text && (
                    <p>
                      {m.source === "voice" && <span className="mr-1">🎙️</span>}
                      {m.text}
                    </p>
                  )}
                  {m.source === "receipt" && !m.text && <p className="text-xs text-indigo-200">Scanning receipt…</p>}
                </div>
              </div>
            );
          if (m.role === "error")
            return (
              <div key={i} className="animate-fade-up max-w-[85%] rounded-2xl rounded-bl-md border border-rose-500/30 bg-rose-500/10 px-4 py-2.5 text-sm text-rose-200">
                Hmm, I couldn't log that: {m.text}
              </div>
            );
          return <ExpenseCard key={i} result={m.result} />;
        })}

        {busy && (
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <Spinner className="h-3.5 w-3.5" /> Thinking…
          </div>
        )}
      </div>

      <form onSubmit={send} data-tour="chat-input" className="border-t border-gray-800 p-3">
        {speech.listening && (
          <div className="mb-2 flex items-center gap-2 rounded-xl bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
            <span className="h-2 w-2 animate-pulse rounded-full bg-rose-400" />
            {speech.interim || "Listening… say something like “I paid 40 bucks for pizza with Alex”"}
          </div>
        )}
        <div className="flex items-end gap-1.5 rounded-2xl border border-gray-700 bg-gray-950 p-2 focus-within:border-indigo-500 focus-within:ring-2 focus-within:ring-indigo-500/20">
          <span data-tour="chat-tools" className="flex gap-1">
          <input ref={fileInput} type="file" accept="image/*" capture="environment" className="hidden" onChange={onReceipt} />
          <button
            type="button"
            onClick={() => fileInput.current?.click()}
            disabled={!group || busy}
            title="Scan a receipt (type a note first to assign items, e.g. “Alex had the steak”)"
            className="flex h-9 w-9 items-center justify-center rounded-xl text-gray-400 transition hover:bg-gray-800 hover:text-gray-100 disabled:opacity-40"
            aria-label="Scan receipt"
          >
            📷
          </button>
          {speech.supported && (
            <button
              type="button"
              onClick={speech.listening ? speech.stop : speech.start}
              disabled={!group || busy}
              title="Speak your expense"
              className={`flex h-9 w-9 items-center justify-center rounded-xl transition disabled:opacity-40 ${
                speech.listening ? "bg-rose-500/20 text-rose-300" : "text-gray-400 hover:bg-gray-800 hover:text-gray-100"
              }`}
              aria-label="Voice input"
            >
              🎙️
            </button>
          )}
          </span>
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
