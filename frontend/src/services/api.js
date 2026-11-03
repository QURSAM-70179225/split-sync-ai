const BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message, status, body) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

async function request(path, { method = "GET", body } = {}) {
  let res;
  try {
    res = await fetch(`${BASE}${path}`, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError("Can't reach the SplitSync API. Is the backend running on :8000?", 0);
  }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    let msg = data?.detail ?? `Request failed (${res.status})`;
    if (Array.isArray(msg)) msg = msg.map((d) => d.msg).join("; ");
    throw new ApiError(msg, res.status, data);
  }
  return data;
}

export const api = {
  health: () => request("/api/health"),
  listGroups: () => request("/api/groups"),
  getGroup: (id) => request(`/api/groups/${id}`),
  createGroup: (name, members) => request("/api/groups", { method: "POST", body: { name, members } }),
  deleteGroup: (id) => request(`/api/groups/${id}`, { method: "DELETE" }),
  addMember: (groupId, name, email) =>
    request(`/api/groups/${groupId}/members`, { method: "POST", body: { name, email: email || null } }),
  parseExpense: (groupId, text, senderId) =>
    request(`/api/groups/${groupId}/expenses/parse`, { method: "POST", body: { text, sender_id: senderId } }),
  listExpenses: (groupId) => request(`/api/groups/${groupId}/expenses`),
  deleteExpense: (id) => request(`/api/expenses/${id}`, { method: "DELETE" }),
  balances: (groupId) => request(`/api/groups/${groupId}/balances`),
  listSettlements: (groupId) => request(`/api/groups/${groupId}/settlements`),
  paySettlement: (payload) => request("/api/settlements/pay", { method: "POST", body: payload }),
  captureSettlement: (id, orderId) =>
    request(`/api/settlements/${id}/capture`, { method: "POST", body: { order_id: orderId || null } }),
  cancelSettlement: (id) => request(`/api/settlements/${id}/cancel`, { method: "POST" }),
};
