import { avatarColor, initials } from "../services/format";

export function Avatar({ user, size = "md" }) {
  const sz = { xs: "h-4 w-4 text-[8px]", sm: "h-6 w-6 text-[10px]", lg: "h-10 w-10 text-sm" }[size] || "h-8 w-8 text-xs";
  return (
    <span
      title={user?.name}
      className={`${sz} ${avatarColor(user?.id)} inline-flex shrink-0 items-center justify-center rounded-full font-semibold text-white ring-2 ring-gray-900`}
    >
      {initials(user?.name)}
    </span>
  );
}

const BADGE = {
  gray: "bg-gray-800 text-gray-300 ring-gray-700",
  indigo: "bg-indigo-500/10 text-indigo-300 ring-indigo-500/30",
  green: "bg-emerald-500/10 text-emerald-300 ring-emerald-500/30",
  red: "bg-rose-500/10 text-rose-300 ring-rose-500/30",
  amber: "bg-amber-500/10 text-amber-300 ring-amber-500/30",
};
export function Badge({ color = "gray", children }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${BADGE[color]}`}>
      {children}
    </span>
  );
}

export function Card({ title, subtitle, action, children, className = "", ...rest }) {
  return (
    <section {...rest} className={`flex min-h-0 flex-col rounded-2xl border border-gray-800 bg-gray-900/60 shadow-xl shadow-black/20 ${className}`}>
      {(title || action) && (
        <header className="flex items-center justify-between gap-3 border-b border-gray-800 px-5 py-3.5">
          <div>
            <h2 className="text-sm font-semibold text-gray-100">{title}</h2>
            {subtitle && <p className="text-xs text-gray-500">{subtitle}</p>}
          </div>
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

export function Spinner({ className = "h-4 w-4" }) {
  return (
    <svg className={`${className} animate-spin`} viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeOpacity=".25" strokeWidth="4" />
      <path d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
    </svg>
  );
}

export function Modal({ open, onClose, title, children }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className="animate-fade-up relative w-full max-w-md rounded-2xl border border-gray-800 bg-gray-900 p-6 shadow-2xl">
        <div className="mb-5 flex items-center justify-between">
          <h3 className="text-lg font-semibold">{title}</h3>
          <button onClick={onClose} className="rounded-lg p-1 text-gray-500 hover:bg-gray-800 hover:text-gray-200" aria-label="Close">
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Toasts({ toasts, dismiss }) {
  const color = { success: "border-emerald-500/40", error: "border-rose-500/40", info: "border-indigo-500/40" };
  const icon = { success: "✅", error: "⚠️", info: "💬" };
  return (
    <div className="fixed right-4 bottom-4 z-[60] flex w-80 flex-col gap-2">
      {toasts.map((t) => (
        <div key={t.id} className={`animate-fade-up flex items-start gap-3 rounded-xl border bg-gray-900 p-3 text-sm shadow-xl ${color[t.type]}`}>
          <span>{icon[t.type]}</span>
          <p className="flex-1 text-gray-200">{t.message}</p>
          <button onClick={() => dismiss(t.id)} className="text-gray-500 hover:text-gray-300">✕</button>
        </div>
      ))}
    </div>
  );
}

export const inputCls =
  "w-full rounded-xl border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-gray-100 placeholder-gray-500 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/30";
export const btnPrimary =
  "inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-indigo-900/40 transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50";
export const btnGhost =
  "inline-flex items-center justify-center gap-2 rounded-xl border border-gray-700 px-3 py-2 text-sm font-medium text-gray-300 transition hover:bg-gray-800 disabled:opacity-50";
