import { useEffect, useState } from "react";
import { api } from "../services/api";
import { money } from "../services/format";
import { Modal, Spinner, btnGhost, btnPrimary } from "./ui";

const TONES = [
  { id: "friendly", label: "😊 Friendly" },
  { id: "funny", label: "😂 Funny" },
  { id: "formal", label: "🎩 Formal" },
];

export default function NudgeModal({ debt, groupId, onClose }) {
  const [tone, setTone] = useState("friendly");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!debt) return;
    let alive = true;
    setBusy(true);
    setCopied(false);
    api
      .nudge(groupId, { from_user_id: debt.from_user.id, to_user_id: debt.to_user.id, amount: debt.amount, currency: debt.currency, tone })
      .then((r) => alive && setMessage(r.message))
      .catch((e) => alive && setMessage(`⚠️ ${e.message}`))
      .finally(() => alive && setBusy(false));
    return () => {
      alive = false;
    };
  }, [debt, groupId, tone]);

  async function copy() {
    try {
      await navigator.clipboard.writeText(message);
      setCopied(true);
    } catch {
      /* clipboard blocked */
    }
  }

  return (
    <Modal open={Boolean(debt)} onClose={onClose} title="Send a nudge">
      {debt && (
        <div className="space-y-4">
          <p className="text-sm text-gray-400">
            AI-written reminder from <span className="text-white">{debt.to_user.name}</span> to{" "}
            <span className="text-white">{debt.from_user.name}</span> for {money(debt.amount, debt.currency)}.
          </p>
          <div className="flex gap-2">
            {TONES.map((t) => (
              <button
                key={t.id}
                onClick={() => setTone(t.id)}
                className={`flex-1 rounded-xl border px-2 py-1.5 text-xs font-medium transition ${
                  tone === t.id ? "border-indigo-500 bg-indigo-500/15 text-indigo-200" : "border-gray-700 text-gray-400 hover:bg-gray-800"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
          <div className="min-h-24 rounded-xl border border-gray-800 bg-gray-950 p-4 text-sm leading-relaxed text-gray-200">
            {busy ? <span className="flex items-center gap-2 text-gray-500"><Spinner /> Writing…</span> : message}
          </div>
          <div className="flex justify-end gap-2">
            <a
              className={btnGhost}
              href={`https://wa.me/?text=${encodeURIComponent(message)}`}
              target="_blank"
              rel="noreferrer"
            >
              WhatsApp
            </a>
            <button className={btnPrimary} onClick={copy} disabled={busy}>
              {copied ? "Copied ✓" : "Copy message"}
            </button>
          </div>
        </div>
      )}
    </Modal>
  );
}
