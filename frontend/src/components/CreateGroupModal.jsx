import { useState } from "react";
import { Modal, btnGhost, btnPrimary, inputCls } from "./ui";

const blank = () => ({ name: "", email: "" });

export default function CreateGroupModal({ open, onClose, onCreate }) {
  const [name, setName] = useState("");
  const [members, setMembers] = useState([{ name: "You", email: "" }, blank(), blank()]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const update = (i, field, value) =>
    setMembers((ms) => ms.map((m, idx) => (idx === i ? { ...m, [field]: value } : m)));

  async function submit(e) {
    e.preventDefault();
    const cleaned = members
      .filter((m) => m.name.trim())
      .map((m) => ({ name: m.name.trim(), email: m.email.trim() || null }));
    if (!name.trim()) return setError("Give your group a name.");
    if (cleaned.length < 2) return setError("Add at least two members.");
    setBusy(true);
    setError("");
    try {
      await onCreate(name.trim(), cleaned);
      setName("");
      setMembers([{ name: "You", email: "" }, blank(), blank()]);
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Create a group">
      <form onSubmit={submit} className="space-y-4">
        <div>
          <label className="mb-1.5 block text-xs font-medium text-gray-400">Group name</label>
          <input className={inputCls} placeholder="Lisbon Trip 🇵🇹" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
        </div>
        <div>
          <label className="mb-1.5 block text-xs font-medium text-gray-400">
            Members <span className="text-gray-600">(email optional — used as PayPal payee)</span>
          </label>
          <div className="scrollbar-thin max-h-64 space-y-2 overflow-y-auto pr-1">
            {members.map((m, i) => (
              <div key={i} className="flex gap-2">
                <input className={`${inputCls} flex-[2]`} placeholder={`Member ${i + 1}`} value={m.name} onChange={(e) => update(i, "name", e.target.value)} />
                <input className={`${inputCls} flex-[3]`} placeholder="email@sandbox.com" type="email" value={m.email} onChange={(e) => update(i, "email", e.target.value)} />
                {members.length > 2 && (
                  <button type="button" onClick={() => setMembers((ms) => ms.filter((_, idx) => idx !== i))} className="px-1 text-gray-500 hover:text-rose-400" aria-label="Remove member">
                    ✕
                  </button>
                )}
              </div>
            ))}
          </div>
          <button type="button" onClick={() => setMembers((ms) => [...ms, blank()])} className="mt-2 text-xs font-medium text-indigo-300 hover:text-indigo-200">
            + Add member
          </button>
        </div>
        {error && <p className="rounded-lg bg-rose-500/10 px-3 py-2 text-sm text-rose-300">{error}</p>}
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" className={btnGhost} onClick={onClose}>Cancel</button>
          <button className={btnPrimary} disabled={busy}>{busy ? "Creating…" : "Create group"}</button>
        </div>
      </form>
    </Modal>
  );
}
