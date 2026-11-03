import { useCallback, useEffect, useRef, useState } from "react";
import BalancesPanel from "./components/BalancesPanel";
import ChatPanel from "./components/ChatPanel";
import CreateGroupModal from "./components/CreateGroupModal";
import Ledger from "./components/Ledger";
import Sidebar from "./components/Sidebar";
import { Avatar, Modal, Spinner, Toasts, btnGhost, btnPrimary, inputCls } from "./components/ui";
import { api } from "./services/api";
import { money, storage } from "./services/format";

export default function App() {
  const [health, setHealth] = useState(null);
  const [groups, setGroups] = useState([]);
  const [activeId, setActiveId] = useState(() => storage.get("splitsync.activeGroup"));
  const [expenses, setExpenses] = useState([]);
  const [settlements, setSettlements] = useState([]);
  const [balances, setBalances] = useState(null);
  const [identity, setIdentity] = useState(() => storage.get("splitsync.identity", {}));
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [showAddMember, setShowAddMember] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [toasts, setToasts] = useState([]);
  const handledReturn = useRef(false);

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
  }, []);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
    loadGroups()
      .catch((e) => toast(e.message, "error"))
      .finally(() => setLoading(false));
  }, [loadGroups, toast]);

  useEffect(() => {
    storage.set("splitsync.activeGroup", activeId);
    setExpenses([]);
    setBalances(null);
    setSettlements([]);
    loadGroupData(activeId).catch((e) => toast(e.message, "error"));
  }, [activeId, loadGroupData, toast]);

  useEffect(() => storage.set("splitsync.identity", identity), [identity]);

  // ---------- PayPal return handling (?paypal=success&settlement_id=..&token=ORDER_ID)
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
    api
      .captureSettlement(sid, params.get("token"))
      .then(async (st) => {
        toast(`Payment of ${money(st.amount, st.currency)} from ${st.from_user.name} to ${st.to_user.name} completed! 🎉`, "success");
        setActiveId(st.group_id);
        await loadGroupData(st.group_id);
      })
      .catch((e) => toast(`Payment capture failed: ${e.message}`, "error"));
  }, [toast, loadGroupData]);

  // ---------- actions
  async function createGroup(name, members) {
    const g = await api.createGroup(name, members);
    await loadGroups();
    setActiveId(g.id);
    toast(`Group “${g.name}” created`, "success");
  }

  async function parseExpense(text) {
    const res = await api.parseExpense(group.id, text, me?.id);
    if (res.new_members.length) await loadGroups();
    await loadGroupData(group.id);
    return res;
  }

  async function deleteExpense(id) {
    if (!window.confirm("Delete this expense?")) return;
    try {
      await api.deleteExpense(id);
      await loadGroupData(group.id);
    } catch (e) {
      toast(e.message, "error");
    }
  }

  async function settle(debt) {
    try {
      const { approval_url } = await api.paySettlement({
        group_id: group.id,
        from_user_id: debt.from_user.id,
        to_user_id: debt.to_user.id,
        amount: debt.amount,
        currency: debt.currency,
      });
      window.location.assign(approval_url); // PayPal sandbox approval page
    } catch (e) {
      toast(e.message, "error");
    }
  }

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
            <h1 className="truncate text-lg font-semibold tracking-tight">{group?.name ?? "SplitSync AI"}</h1>
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
          {group && (
            <label className="flex items-center gap-2 text-xs text-gray-400">
              Acting as
              <select
                value={me?.id ?? ""}
                onChange={(e) => setIdentity((ids) => ({ ...ids, [group.id]: Number(e.target.value) }))}
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
            <h2 className="mt-4 text-2xl font-semibold">Split expenses by just talking</h2>
            <p className="mt-2 max-w-md text-sm text-gray-400">
              Create a group, type “I paid $60 for dinner with Alex and Sarah”, and SplitSync AI handles the math — then settle up instantly with PayPal.
            </p>
            <button className={`${btnPrimary} mt-6`} onClick={() => setShowCreate(true)}>Create your first group</button>
          </div>
        ) : (
          <div className="grid flex-1 grid-cols-1 gap-5 overflow-y-auto p-4 sm:p-6 xl:grid-cols-12">
            <div className="h-[36rem] xl:sticky xl:top-0 xl:col-span-5 xl:h-[calc(100vh-8rem)]">
              <ChatPanel group={group} me={me} parseExpense={parseExpense} />
            </div>
            <div className="space-y-5 xl:col-span-7">
              <BalancesPanel balances={balances} me={me} onSettle={settle} />
              <Ledger expenses={expenses} settlements={settlements} onDelete={deleteExpense} />
            </div>
          </div>
        )}
      </main>

      <CreateGroupModal open={showCreate} onClose={() => setShowCreate(false)} onCreate={createGroup} />
      <AddMemberModal
        open={showAddMember}
        onClose={() => setShowAddMember(false)}
        onAdd={async (name, email) => {
          await api.addMember(group.id, name, email);
          await loadGroups();
          await loadGroupData(group.id);
          toast(`${name} joined ${group.name}`, "success");
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
