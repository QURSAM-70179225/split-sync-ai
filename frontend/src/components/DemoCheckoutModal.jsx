import { useState } from "react";
import { money } from "../services/format";
import { Spinner } from "./ui";

/**
 * Shown when the backend runs with PAYPAL_MODE=demo (no sandbox credentials):
 * simulates the PayPal approval step so the full settle-up flow can be demoed offline.
 */
export default function DemoCheckoutModal({ checkout, onApprove, onCancel }) {
  const [busy, setBusy] = useState(false);
  if (!checkout) return null;
  const { settlement } = checkout;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
      <div className="animate-fade-up relative w-full max-w-sm overflow-hidden rounded-2xl bg-white text-gray-900 shadow-2xl">
        <div className="flex items-center justify-between bg-gradient-to-r from-indigo-600 to-violet-600 px-5 py-3 text-white">
          <span className="text-sm font-semibold">💸 SplitSync · Simulated checkout</span>
          <span className="rounded bg-amber-400 px-2 py-0.5 text-[10px] font-bold text-amber-950">DEMO MODE</span>
        </div>
        <div className="space-y-4 p-6">
          <div className="text-center">
            <p className="text-sm text-gray-500">{settlement.from_user.name} is paying {settlement.to_user.name}</p>
            <p className="mt-1 text-4xl font-bold">{money(settlement.amount, settlement.currency)}</p>
            <p className="mt-1 font-mono text-[11px] text-gray-400">Order {settlement.paypal_order_id}</p>
          </div>
          <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">
            This stands in for PayPal's approval page — no real money moves. Add PayPal Sandbox keys to <code>backend/.env</code> to use the real PayPal flow.
          </p>
          <button
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              try {
                await onApprove();
              } finally {
                setBusy(false);
              }
            }}
            className="flex w-full items-center justify-center gap-2 rounded-full bg-indigo-600 py-3 font-bold text-white hover:bg-indigo-500 disabled:opacity-60"
          >
            {busy ? <Spinner /> : null} Approve demo payment
          </button>
          <button onClick={onCancel} disabled={busy} className="w-full text-sm text-gray-500 hover:text-gray-800">
            Cancel and return to SplitSync
          </button>
        </div>
      </div>
    </div>
  );
}
