import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Spinner } from "./ui";

/**
 * Spotlight guided tour.
 * steps: [{ id, target?: "data-tour id", title, body, before?: () => void, placement?: "auto" }]
 * Steps without a target (or whose target isn't visible) render as a centered card.
 */
const PAD = 8;
const CARD_W = 340;

function findTarget(id) {
  if (!id) return null;
  const el = document.querySelector(`[data-tour="${id}"]`);
  if (!el) return null;
  const r = el.getBoundingClientRect();
  const visible = r.width > 0 && r.height > 0 && r.right > 0 && r.left < window.innerWidth;
  return visible ? el : null;
}

function waitForTarget(id, timeout = 1200) {
  return new Promise((resolve) => {
    const start = performance.now();
    const tick = () => {
      const el = findTarget(id);
      if (el || performance.now() - start > timeout) resolve(el);
      else requestAnimationFrame(tick);
    };
    tick();
  });
}

function placeCard(rect, cardH = 300) {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const w = Math.min(CARD_W, vw - 32);
  if (!rect || vw < 640) {
    // centered card, or a bottom sheet on phones
    return rect && vw < 640
      ? { left: 16, width: vw - 32, bottom: 16 }
      : { left: (vw - w) / 2, top: Math.max(16, vh / 2 - 140), width: w };
  }
  const clampX = (x) => Math.min(Math.max(16, x), vw - w - 16);
  const below = vh - rect.bottom;
  const above = rect.top;
  const right = vw - rect.right;
  const clampY = (y) => Math.max(16, Math.min(y, vh - cardH - 16));
  if (below > cardH + PAD + 28) return { left: clampX(rect.left), top: rect.bottom + PAD + 12, width: w };
  if (right > w + 40) return { left: rect.right + PAD + 12, top: clampY(rect.top), width: w };
  if (above > cardH + PAD + 28) return { left: clampX(rect.left), bottom: vh - rect.top + PAD + 12, width: w };
  if (rect.left > w + 40) return { left: rect.left - w - PAD - 12, top: clampY(rect.top), width: w };
  return { left: (vw - w) / 2, bottom: 16, width: w };
}

export default function GuidedTour({ open, steps, onClose, hasGroup, onSeed }) {
  const [index, setIndex] = useState(0);
  const [rect, setRect] = useState(null);
  const [busy, setBusy] = useState(false);
  const [ready, setReady] = useState(false);
  const [cardH, setCardH] = useState(300);
  const targetRef = useRef(null);
  const direction = useRef(1);
  const cardRef = useRef(null);

  const step = steps[index];
  const isFirst = index === 0;
  const isLast = index === steps.length - 1;

  const measure = useCallback(() => {
    const el = targetRef.current;
    if (!el || !el.isConnected) return setRect(null);
    const r = el.getBoundingClientRect();
    setRect({ top: r.top, left: r.left, width: r.width, height: r.height, bottom: r.bottom, right: r.right });
  }, []);

  // Resolve the current step's target (running its `before` hook first).
  useEffect(() => {
    if (!open || !step) return;
    let cancelled = false;
    setReady(false);
    (async () => {
      step.before?.();
      const el = await waitForTarget(step.target, step.before ? 1200 : 500);
      if (cancelled) return;
      if (step.target && !el) {
        // Target not on screen (e.g. sidebar hidden on mobile): skip this step.
        setIndex((i) => Math.min(Math.max(i + direction.current, 0), steps.length - 1));
        return;
      }
      targetRef.current = el;
      if (el) {
        el.scrollIntoView({ block: "center", inline: "nearest", behavior: "smooth" });
        setTimeout(() => !cancelled && measure(), 350);
      }
      measure();
      setReady(true);
    })();
    return () => {
      cancelled = true;
    };
  }, [open, step, measure, steps.length]);

  useLayoutEffect(() => {
    if (!open) return;
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, true);
    return () => {
      window.removeEventListener("resize", measure);
      window.removeEventListener("scroll", measure, true);
    };
  }, [open, measure]);

  useEffect(() => {
    if (open) {
      direction.current = 1;
      setIndex(0);
    }
  }, [open]);

  useEffect(() => {
    cardRef.current?.focus();
  }, [index, open]);

  useLayoutEffect(() => {
    const h = cardRef.current?.offsetHeight;
    if (h && Math.abs(h - cardH) > 4) setCardH(h);
  });

  const finish = useCallback(() => {
    targetRef.current = null;
    setRect(null);
    onClose();
  }, [onClose]);

  const next = useCallback(async () => {
    if (busy) return;
    if (isFirst && !hasGroup) {
      setBusy(true);
      try {
        await onSeed();
      } finally {
        setBusy(false);
      }
    }
    direction.current = 1;
    if (isLast) finish();
    else setIndex((i) => i + 1);
  }, [busy, isFirst, isLast, hasGroup, onSeed, finish]);

  const back = useCallback(() => {
    direction.current = -1;
    setIndex((i) => Math.max(0, i - 1));
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e) => {
      if (e.key === "Escape") finish();
      else if (e.key === "ArrowRight" || e.key === "Enter") {
        e.preventDefault();
        next();
      } else if (e.key === "ArrowLeft") back();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, next, back, finish]);

  if (!open || !step) return null;
  if (!ready) return <div className="fixed inset-0 z-[70] bg-gray-950/80" />;

  const spot = rect && targetRef.current ? rect : null;
  const card = placeCard(spot, cardH);

  return (
    <div className="fixed inset-0 z-[70]" aria-live="polite">
      {/* click shield */}
      <div className="absolute inset-0" onClick={(e) => e.stopPropagation()} />
      {spot ? (
        <div
          className="pointer-events-none absolute rounded-2xl ring-2 ring-indigo-400 transition-all duration-300 ease-out"
          style={{
            top: spot.top - PAD,
            left: spot.left - PAD,
            width: spot.width + PAD * 2,
            height: spot.height + PAD * 2,
            boxShadow: "0 0 0 9999px rgba(3, 7, 18, 0.78), 0 0 32px 4px rgba(99, 102, 241, 0.45)",
          }}
        />
      ) : (
        <div className="absolute inset-0 bg-gray-950/80 backdrop-blur-sm" />
      )}

      <div
        ref={cardRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-labelledby="tour-title"
        className="animate-fade-up absolute rounded-2xl border border-indigo-500/40 bg-gray-900 p-5 shadow-2xl shadow-indigo-950/60 outline-none"
        style={card}
        key={step.id}
      >
        <div className="mb-3 flex items-center justify-between gap-3">
          <span className="rounded-full bg-indigo-500/15 px-2 py-0.5 text-[11px] font-semibold text-indigo-300">
            {index + 1} / {steps.length}
          </span>
          <button onClick={finish} className="text-xs text-gray-500 hover:text-gray-300">
            Skip tour
          </button>
        </div>
        {step.icon && <p className="mb-1 text-3xl">{step.icon}</p>}
        <h3 id="tour-title" className="text-base font-semibold text-white">
          {step.title}
        </h3>
        <div className="mt-1.5 text-sm leading-relaxed text-gray-300">{step.body}</div>
        {step.tryIt && (
          <p className="mt-3 rounded-lg border border-gray-800 bg-gray-950 px-3 py-2 font-mono text-xs text-indigo-200">
            💬 {step.tryIt}
          </p>
        )}

        <div className="mt-4 flex items-center gap-3">
          <div className="flex flex-1 flex-wrap gap-1">
            {steps.map((s, i) => (
              <span key={s.id} className={`h-1.5 rounded-full transition-all ${i === index ? "w-4 bg-indigo-400" : i < index ? "w-1.5 bg-indigo-400/50" : "w-1.5 bg-gray-700"}`} />
            ))}
          </div>
          {!isFirst && (
            <button onClick={back} className="rounded-lg px-3 py-1.5 text-sm text-gray-400 hover:bg-gray-800 hover:text-gray-200">
              Back
            </button>
          )}
          <button
            onClick={next}
            disabled={busy}
            className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-1.5 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-60"
          >
            {busy && <Spinner className="h-3.5 w-3.5" />}
            {isFirst ? (hasGroup ? "Start tour" : "Load demo & start") : isLast ? "Start splitting 🚀" : "Next"}
          </button>
        </div>
        <p className="mt-3 hidden text-[10px] text-gray-600 sm:block">Tip: use ← → to navigate, Esc to close.</p>
      </div>
    </div>
  );
}
