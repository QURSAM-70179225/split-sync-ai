import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import BalancesPanel from "./components/BalancesPanel";
import ChatPanel from "./components/ChatPanel";
import CreateGroupModal from "./components/CreateGroupModal";
import DemoCheckoutModal from "./components/DemoCheckoutModal";
import GuidedTour from "./components/GuidedTour";
import InsightsPanel from "./components/InsightsPanel";
import Ledger from "./components/Ledger";
import NudgeModal from "./components/NudgeModal";
import Sidebar from "./components/Sidebar";
import { Avatar, Modal, Spinner, Toasts, btnGhost, btnPrimary, inputCls } from "./components/ui";
import { useGroupEvents } from "./hooks/useGroupEvents";
import { api } from "./services/api";
import { money, storage } from "./services/format";
import { buildTourSteps } from "./services/tourSteps";

const LIVE_EVENT_TEXT = {
  "expense.created": (e) => `${e.by ? `${e.by} added` : "New expense:"} ${e.description}`,
  "expense.deleted": () => "An expense was removed",
  "settlement.completed": (e) => `${e.from} paid ${e.to} ${money(e.amount)} 🎉`,
  "member.added": (e) => `${e.name} joined the group`,
};

export default function App() {
  const [health, setHealth] = useState(null);
  const [groups, setGroups] = useState([]);
  const [activeId, setActiveId] = useState(() => storage.get("splitsync.activeGroup"));
  const [expenses, setExpenses] = useState([]);
  const [settlements, setSettlements] = useState([]);
  const [balances, setBalances] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [identity, setIdentity] = useState(() => storage.get("splitsync.identity", {}));
  const [tab, setTab] = useState(() => storage.get("splitsync.tab", "overview"));
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [showAddMember, setShowAddMember] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [nudgeDebt, setNudgeDebt] = useState(null);
  const [demoCheckout, setDemoCheckout] = useState(null);
  const [toasts, setToasts] = useState([]);
  const [tourOpen, setTourOpen] = useState(false);
  const handledReturn = useRef(false);
  const lastLocalAction = useRef(0);

  const toast = useCallback((message, type = "info") => {
    const id = Math.random().toString(36).slice(2);
    setToasts((t) => [...t, { id, message, type }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 6000);
  }, []);

  const group = groups.find((g) => g.id === activeId) || null;
  const me = group?.members.find((m) => m.id === identity[group.id]) || group?.members[0] || null;

  // ---------- data loading
  const loadGroups = useCallback(async () => {
    const list = await api.listGroups();
    setGroups(list);
    setActiveId((cur) => (list.some((g) => g.id === cur) ? cur : list[0]?.id ?? null));
    return list;
  }, []);

  const loadGroupData = useCallback(async (id) => {
    if (!id) return;
    const [ex, bal, st] = await Promise.all([api.listExpenses(id), api.balances(id), api.listSettlements(id)]);
    setExpenses(ex);
    setBalances(bal);
    setSettlements(st);
    setRefreshKey((k) => k + 1);
  }, []);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
    loadGroups()
      .catch((e) => toast(e.message, "error"))
      .finally(() => {
        setLoading(false);
        const fromPayPal = new URLSearchParams(window.location.search).has("paypal");
        if (!storage.get("splitsync.tourDone", false) && !fromPayPal) setTimeout(() => setTourOpen(true), 600);
      });
  }, [loadGroups, toast]);

  useEffect(() => {
    storage.set("splitsync.activeGroup", activeId);
    setExpenses([]);
    setBalances(null);
    setSettlements([]);
    loadGroupData(activeId).catch((e) => toast(e.message, "error"));
  }, [activeId, loadGroupData, toast]);

  useEffect(() => storage.set("splitsync.identity", identity), [identity]);
  useEffect(() => storage.set("splitsync.tab", tab), [tab]);

  // ---------- live sync: other devices' changes appear instantly
  const live = useGroupEvents(activeId, (evt) => {
    if (evt.type === "group.deleted") {
      loadGroups();
      return;
    }
    if (evt.type === "member.added") loadGroups();
    loadGroupData(activeId);
    const fromElsewhere = Date.now() - lastLocalAction.current > 2500;
    if (fromElsewhere && LIVE_EVENT_TEXT[evt.type]) toast(`🔴 Live: ${LIVE_EVENT_TEXT[evt.type](evt)}`, "info");
  });
  const touch = () => (lastLocalAction.current = Date.now());

  // ---------- PayPal return handling (?paypal=success&settlement_id=..&token=ORDER_ID)
  const capture = useCallback(
    async (sid, orderId) => {
      touch();
      const st = await api.captureSettlement(sid, orderId);
      toast(`Payment of ${money(st.amount, st.currency)} from ${st.from_user.name} to ${st.to_user.name} completed! 🎉`, "success");
      setActiveId(st.group_id);
      await loadGroupData(st.group_id);
    },
    [toast, loadGroupData]
  );

  useEffect(() => {
    if (handledReturn.current) return;
    const params = new URLSearchParams(window.location.search);
    const status = params.get("paypal");
    const sid = params.get("settlement_id");
    if (!status || !sid) return;
    handledReturn.current = true;
    window.history.replaceState({}, "", window.location.pathname);

    if (status === "cancel") {
      api.cancelSettlement(sid).catch(() => {});
      toast("PayPal checkout was cancelled — nothing was charged.", "info");
      return;
    }
    toast("Confirming your PayPal payment…", "info");
    capture(sid, params.get("token")).catch((e) => toast(`Payment capture failed: ${e.message}`, "error"));
  }, [toast, capture]);

  // ---------- actions
  async function createGroup(name, members) {
    const g = await api.createGroup(name, members);
    await loadGroups();
    setActiveId(g.id);
    toast(`Group “${g.name}” created`, "success");
  }

  async function seedDemo() {
    setSeeding(true);
    try {
      const g = await api.seedDemo();
      await loadGroups();
      setActiveId(g.id);
      toast("Demo trip loaded — explore balances, insights and settle up!", "success");
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setSeeding(false);
    }
  }

  async function afterExpense(res) {
    if (res.new_members.length) await loadGroups();
    await loadGroupData(group.id);
    return res;
  }

  async function parseExpense(text, source) {
    touch();
    return afterExpense(await api.parseExpense(group.id, text, me?.id, source));
  }

  async function scanReceipt(file, note) {
    touch();
    return afterExpense(await api.scanReceipt(group.id, file, note, me?.id));
  }

  async function deleteExpense(id) {
    if (!window.confirm("Delete this expense?")) return;
    try {
      touch();
      await api.deleteExpense(id);
      await loadGroupData(group.id);
    } catch (e) {
      toast(e.message, "error");
    }
  }

  async function settle(debt) {
    try {
      const res = await api.paySettlement({
        group_id: group.id,
        from_user_id: debt.from_user.id,
        to_user_id: debt.to_user.id,
        amount: debt.amount,
        currency: debt.currency,
      });
      if (res.mode === "demo") setDemoCheckout(res);
      else window.location.assign(res.approval_url); // real PayPal sandbox approval page
    } catch (e) {
      toast(e.message, "error");
    }
  }

  const tourSteps = useMemo(() => buildTourSteps({ showTab: setTab }), []);

  const liveDot = { live: "bg-emerald-400", connecting: "bg-amber-400 animate-pulse", offline: "bg-gray-600" }[live.status];

  return (
    <div className="flex h-full">
      <Sidebar
        groups={groups}
        activeId={activeId}
        onSelect={(id) => {
          setActiveId(id);
          setSidebarOpen(false);
        }}
        onCreate={() => setShowCreate(true)}
        onSeed={seedDemo}
        seeding={seeding}
        health={health}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      <main className="flex min-w-0 flex-1 flex-col overflow-hidden bg-[radial-gradient(ellipse_at_top,_rgba(99,102,241,0.08),_transparent_60%)]">
        <header className="flex flex-wrap items-center gap-3 border-b border-gray-800 px-4 py-3.5 sm:px-6">
          <button className="rounded-lg p-2 text-gray-400 hover:bg-gray-800 lg:hidden" onClick={() => setSidebarOpen(true)} aria-label="Open menu">
            ☰
          </button>
          <div className="min-w-0 flex-1">
            <h1 className="flex items-center gap-2 truncate text-lg font-semibold tracking-tight">
              {group?.name ?? "SplitSync AI"}
              {group && (
                <span
                  data-tour="live"
                  title={live.status === "live" ? "Live sync on — changes from other devices appear instantly" : "Reconnecting…"}
                  className="flex items-center gap-1.5 rounded-full border border-gray-800 px-2 py-0.5 text-[10px] font-medium text-gray-400"
                >
                  <span className={`h-1.5 w-1.5 rounded-full ${liveDot}`} />
                  {live.status === "live" ? "LIVE" : "SYNCING"}
                </span>
              )}
            </h1>
            {group && (
              <div className="mt-1 flex items-center gap-2">
                <div className="flex -space-x-2">
                  {group.members.map((m) => (
                    <Avatar key={m.id} user={m} size="sm" />
                  ))}
                </div>
                <button onClick={() => setShowAddMember(true)} className="text-xs text-gray-500 hover:text-indigo-300">+ member</button>
              </div>
            )}
          </div>
          <button
            onClick={() => {
              setSidebarOpen(false);
              setTourOpen(true);
            }}
            className="rounded-lg border border-gray-700 px-2.5 py-1.5 text-xs font-medium text-gray-300 transition hover:border-indigo-500/50 hover:text-white"
            title="Take the guided tour"
          >
            ❔<span className="hidden sm:inline"> Tour</span>
          </button>
          {group && (
            <label data-tour="acting-as" className="flex items-center gap-2 text-xs text-gray-400">
              <span className="hidden sm:inline">Acting as</span>
              <select
                value={me?.id ?? ""}
                onChange={(e) => setIdentity((ids) => ({ ...ids, [group.id]: Number(e.target.value) }))}
                aria-label="Acting as"
                className="rounded-lg border border-gray-700 bg-gray-900 px-2 py-1.5 text-sm text-gray-100 outline-none focus:border-indigo-500"
              >
                {group.members.map((m) => (
                  <option key={m.id} value={m.id}>{m.name}</option>
                ))}
              </select>
            </label>
          )}
        </header>

        {loading ? (
          <div className="flex flex-1 items-center justify-center text-gray-500"><Spinner className="h-6 w-6" /></div>
        ) : !group ? (
          <div className="flex flex-1 flex-col items-center justify-center p-6 text-center">
            <p className="text-5xl">💸</p>
            <h2 className="mt-4 text-2xl font-semibold sm:text-3xl">Split expenses by just talking</h2>
            <p className="mt-2 max-w-md text-sm text-gray-400">
              Type it, say it, or snap the receipt. SplitSync AI does the math, finds the fewest payments, and settles up with PayPal in one tap.
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-3">
              <button className={btnPrimary} onClick={() => setShowCreate(true)}>Create your first group</button>
              <button className={btnGhost} onClick={seedDemo} disabled={seeding}>
                {seeding ? <Spinner /> : "🌴"} Load demo trip
              </button>
              <button className={btnGhost} onClick={() => setTourOpen(true)}>
                ❔ Take the tour
              </button>
            </div>
            <div className="mt-10 grid max-w-2xl grid-cols-1 gap-3 text-left sm:grid-cols-3">
              {[
                ["🗣️", "Conversational", "Natural language, voice, and receipt photos — the AI parses them all."],
                ["⚡", "Smart settlement", "Debts simplified to the minimum number of payments."],
                ["💳", "One-tap PayPal", "Settle each debt via PayPal checkout, synced live for everyone."],
              ].map(([icon, title, body]) => (
                <div key={title} className="rounded-2xl border border-gray-800 bg-gray-900/50 p-4">
                  <p className="text-xl">{icon}</p>
                  <p className="mt-2 text-sm font-semibold">{title}</p>
                  <p className="mt-1 text-xs text-gray-400">{body}</p>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="grid flex-1 grid-cols-1 gap-5 overflow-y-auto p-4 sm:p-6 xl:grid-cols-12">
            <div className="h-[36rem] xl:sticky xl:top-0 xl:col-span-5 xl:h-[calc(100vh-8rem)]">
              <ChatPanel group={group} me={me} parseExpense={parseExpense} scanReceipt={scanReceipt} />
            </div>
            <div className="space-y-5 xl:col-span-7">
              <div className="flex gap-1 rounded-xl border border-gray-800 bg-gray-900/60 p-1" role="tablist">
                {[
                  ["overview", "⚖️ Balances & Activity"],
                  ["insights", "📊 Insights & AI Copilot"],
                ].map(([id, label]) => (
                  <button
                    key={id}
                    role="tab"
                    aria-selected={tab === id}
                    onClick={() => setTab(id)}
                    className={`flex-1 rounded-lg px-3 py-2 text-sm font-medium transition ${tab === id ? "bg-indigo-600 text-white shadow" : "text-gray-400 hover:text-gray-200"}`}
                  >
                    {label}
                  </button>
                ))}
              </div>
              {tab === "overview" ? (
                <>
                  <BalancesPanel balances={balances} me={me} onSettle={settle} onNudge={setNudgeDebt} />
                  <Ledger groupId={group.id} expenses={expenses} settlements={settlements} onDelete={deleteExpense} />
                </>
              ) : (
                <InsightsPanel groupId={group.id} me={me} refreshKey={refreshKey} />
              )}
            </div>
          </div>
        )}
      </main>

      <CreateGroupModal open={showCreate} onClose={() => setShowCreate(false)} onCreate={createGroup} />
      <AddMemberModal
        open={showAddMember}
        onClose={() => setShowAddMember(false)}
        onAdd={async (name, email) => {
          touch();
          await api.addMember(group.id, name, email);
          await loadGroups();
          await loadGroupData(group.id);
          toast(`${name} joined ${group.name}`, "success");
        }}
      />
      <NudgeModal debt={nudgeDebt} groupId={group?.id} onClose={() => setNudgeDebt(null)} />
      <DemoCheckoutModal
        checkout={demoCheckout}
        onApprove={async () => {
          try {
            await capture(demoCheckout.settlement.id, demoCheckout.settlement.paypal_order_id);
          } catch (e) {
            toast(`Payment failed: ${e.message}`, "error");
          }
          setDemoCheckout(null);
        }}
        onCancel={() => {
          api.cancelSettlement(demoCheckout.settlement.id).catch(() => {});
          setDemoCheckout(null);
          toast("Checkout cancelled — nothing was charged.", "info");
        }}
      />
      <GuidedTour
        open={tourOpen}
        steps={tourSteps}
        hasGroup={Boolean(group)}
        onSeed={seedDemo}
        onClose={() => {
          setTourOpen(false);
          storage.set("splitsync.tourDone", true);
        }}
      />
      <Toasts toasts={toasts} dismiss={(id) => setToasts((t) => t.filter((x) => x.id !== id))} />
    </div>
  );
}

function AddMemberModal({ open, onClose, onAdd }) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    setError("");
    try {
      await onAdd(name.trim(), email.trim());
      setName("");
      setEmail("");
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Add a member">
      <form onSubmit={submit} className="space-y-3">
        <input className={inputCls} placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
        <input className={inputCls} placeholder="Email (optional)" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        {error && <p className="text-sm text-rose-300">{error}</p>}
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" className={btnGhost} onClick={onClose}>Cancel</button>
          <button className={btnPrimary} disabled={busy}>Add</button>
        </div>
      </form>
    </Modal>
  );
}
