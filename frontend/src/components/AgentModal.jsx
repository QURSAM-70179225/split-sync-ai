import { useEffect, useState } from "react";
import { api } from "../services/api";
import { aiLabel, money } from "../services/format";
import { Avatar, Badge, Modal, Spinner, btnGhost, btnPrimary } from "./ui";

const SUGGESTIONS = ["Settle everything for me", "Pay all my debts", "Remind everyone who owes me"];

/**
 * Settle-Up Agent: command → plan (amounts from the ledger) → user confirms → PayPal orders
 * are created and approved one by one. `run` (the executed plan) lives in App so it survives
 * the redirect to PayPal and back.
 */
export default function AgentModal({ open, onClose, group, me, initialText, run, onRun, onApprove, onClearRun }) {
  const [text, setText] = useState("");
  const [plan, setPlan] = useState(null);
  const [selected, setSelected] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(null);

  useEffect(() => {
    if (!open) return;
    setError("");
    if (initialText) {
      setText(initialText);
      makePlan(initialText);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, initialText]);

  async function makePlan(command) {
    const value = (command ?? text).trim();
    if (!value || !group || !me) return;
    setBusy(true);
    setError("");
    setPlan(null);
    try {
      const p = await api.agentPlan(group.id, value, me.id);
      setPlan(p);
      setSelected(p.actions.map((_, i) => i));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function confirm() {
    const actions = plan.actions
      .filter((_, i) => selected.includes(i))
      .map((a) => ({ kind: a.kind, from_user_id: a.from_user.id, to_user_id: a.to_user.id, amount: a.amount, currency: a.currency }));
    if (!actions.length) return;
    setBusy(true);
    setError("");
    try {
      const out = await api.agentExecute(group.id, me.id, actions);
      onRun({ groupId: group.id, mode: out.mode, payments: out.payments.map((p) => ({ ...p, status: "pending" })), nudges: out.nudges });
      setPlan(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    onClearRun();
    setPlan(null);
    setText("");
  }

  const toggle = (i) => setSelected((s) => (s.includes(i) ? s.filter((x) => x !== i) : [...s, i]));
  const nextPending = run?.payments.find((p) => p.status === "pending");
  const allPaid = run && run.payments.length > 0 && run.payments.every((p) => p.status === "paid");
  const finished = run && !nextPending;

  return (
    <Modal open={open} onClose={onClose} title="🤖 Settle-Up Agent">
      {!run && (
        <div className="space-y-4">
          <p className="text-sm text-gray-400">
            Tell me what to do and I'll plan it. <span className="text-gray-300">Amounts come from your ledger, and nothing happens until you confirm.</span>
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              makePlan();
            }}
            className="flex gap-2"
          >
            <input
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder={`e.g. Settle everything for me${me ? ` (as ${me.name})` : ""}`}
              className="flex-1 rounded-xl border border-gray-700 bg-gray-950 px-3 py-2 text-sm outline-none focus:border-indigo-500"
              aria-label="Agent command"
            />
            <button className={btnPrimary} disabled={busy || !text.trim()}>
              {busy ? <Spinner /> : "Plan"}
            </button>
          </form>
          {!plan && (
            <div className="flex flex-wrap gap-1.5">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => {
                    setText(s);
                    makePlan(s);
                  }}
                  className="rounded-full border border-gray-700 px-2.5 py-1 text-[11px] text-gray-400 hover:border-indigo-500/50 hover:text-gray-200"
                >
                  {s}
                </button>
              ))}
            </div>
          )}

          {plan && (
            <div className="animate-fade-up space-y-3 rounded-xl border border-indigo-500/30 bg-indigo-500/5 p-4" data-testid="agent-plan">
              <p className="text-sm text-gray-200">{plan.summary}</p>
              {plan.actions.length > 0 && (
                <ul className="space-y-2">
                  {plan.actions.map((a, i) => (
                    <li key={i}>
                      <label className="flex cursor-pointer items-center gap-3 rounded-lg border border-gray-800 bg-gray-950/60 px-3 py-2">
                        <input type="checkbox" checked={selected.includes(i)} onChange={() => toggle(i)} className="accent-indigo-500" />
                        <Avatar user={a.kind === "pay" ? a.to_user : a.from_user} size="sm" />
                        <span className="flex-1 text-sm text-gray-200">
                          {a.kind === "pay" ? (
                            <>💳 Pay <b>{a.to_user.name}</b> via PayPal</>
                          ) : (
                            <>🔔 Remind <b>{a.from_user.name}</b></>
                          )}
                        </span>
                        <span className="font-mono text-sm text-gray-100">{money(a.amount, a.currency)}</span>
                      </label>
                    </li>
                  ))}
                </ul>
              )}
              <div className="flex items-center justify-between gap-2 pt-1">
                <Badge color={plan.ai_mode === "offline" ? "amber" : "green"}>
                  {plan.ai_mode === "offline" ? "Keyword fallback" : `✨ ${aiLabel(plan.ai_mode)}`}
                </Badge>
                {plan.actions.length > 0 && (
                  <button className={btnPrimary} onClick={confirm} disabled={busy || !selected.length}>
                    {busy ? <Spinner /> : null} Confirm &amp; run ({selected.length})
                  </button>
                )}
              </div>
            </div>
          )}
          {error && <p className="rounded-lg bg-rose-500/10 px-3 py-2 text-sm text-rose-300">{error}</p>}
        </div>
      )}

      {run && (
        <div className="space-y-4" data-testid="agent-run">
          {run.payments.length > 0 && (
            <div>
              <p className="mb-2 text-xs font-semibold tracking-wider text-gray-500 uppercase">
                PayPal payments · {run.payments.filter((p) => p.status === "paid").length}/{run.payments.length} done
              </p>
              <ul className="space-y-2">
                {run.payments.map((p) => {
                  const st = p.settlement;
                  const isNext = nextPending && nextPending.settlement.id === st.id;
                  return (
                    <li key={st.id} className={`flex items-center gap-3 rounded-lg border px-3 py-2 ${isNext ? "border-indigo-500/50 bg-indigo-500/10" : "border-gray-800 bg-gray-950/60"}`}>
                      <Avatar user={st.to_user} size="sm" />
                      <span className="flex-1 text-sm text-gray-200">
                        Pay <b>{st.to_user.name}</b> <span className="font-mono">{money(st.amount, st.currency)}</span>
                      </span>
                      {p.status === "paid" ? (
                        <Badge color="green">✓ paid</Badge>
                      ) : p.status === "cancelled" ? (
                        <Badge color="red">cancelled</Badge>
                      ) : isNext ? (
                        <button className={`${btnPrimary} !px-3 !py-1.5 !text-xs`} onClick={() => onApprove(p)}>
                          Approve in PayPal →
                        </button>
                      ) : (
                        <Badge>waiting</Badge>
                      )}
                    </li>
                  );
                })}
              </ul>
            </div>
          )}

          {run.nudges.length > 0 && (
            <div>
              <p className="mb-2 text-xs font-semibold tracking-wider text-gray-500 uppercase">Reminders written for you</p>
              <ul className="space-y-2">
                {run.nudges.map((n, i) => (
                  <li key={i} className="rounded-lg border border-gray-800 bg-gray-950/60 p-3">
                    <p className="mb-1 text-xs text-gray-500">
                      To <b className="text-gray-300">{n.to_user.name}</b> · {money(n.amount, n.currency)}
                    </p>
                    <p className="text-sm text-gray-200">{n.message}</p>
                    <div className="mt-2 flex justify-end gap-2">
                      <a className={`${btnGhost} !py-1 !text-xs`} href={`https://wa.me/?text=${encodeURIComponent(n.message)}`} target="_blank" rel="noreferrer">
                        WhatsApp
                      </a>
                      <button
                        className={`${btnGhost} !py-1 !text-xs`}
                        onClick={async () => {
                          try {
                            await navigator.clipboard.writeText(n.message);
                            setCopied(i);
                          } catch {
                            /* clipboard blocked */
                          }
                        }}
                      >
                        {copied === i ? "Copied ✓" : "Copy"}
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {allPaid && (
            <p className="rounded-lg bg-emerald-500/10 px-3 py-2 text-sm text-emerald-200">🎉 All done: every payment in the plan went through PayPal.</p>
          )}
          <div className="flex justify-end">
            <button className={btnGhost} onClick={reset}>
              {finished ? "New command" : "Cancel remaining"}
            </button>
          </div>
        </div>
      )}
    </Modal>
  );
}
