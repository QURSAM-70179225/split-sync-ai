/** "groq:llama-3.3-70b-versatile" -> "Groq · llama-3.3-70b-versatile"; "offline" -> "Offline fallback" */
export function aiLabel(mode = "offline") {
  if (!mode || mode === "offline") return "Offline fallback";
  const [provider, model] = mode.split(":");
  const name = { groq: "Groq", gemini: "Gemini" }[provider] || provider;
  return model ? `${name} · ${model.split("/").pop()}` : name;
}

export function money(amount, currency = "USD") {
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(amount);
  } catch {
    return `${Number(amount).toFixed(2)} ${currency}`;
  }
}

export function timeAgo(iso) {
  const date = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : `${iso}Z`);
  const s = Math.round((Date.now() - date.getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

const PALETTE = [
  "bg-indigo-500", "bg-emerald-500", "bg-rose-500", "bg-amber-500",
  "bg-sky-500", "bg-fuchsia-500", "bg-teal-500", "bg-orange-500",
];
export const avatarColor = (id) => PALETTE[(id ?? 0) % PALETTE.length];
export const initials = (name = "?") =>
  name.split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0].toUpperCase()).join("");

export const storage = {
  get(key, fallback = null) {
    try {
      const v = localStorage.getItem(key);
      return v === null ? fallback : JSON.parse(v);
    } catch {
      return fallback;
    }
  },
  set(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      /* ignore */
    }
  },
};
