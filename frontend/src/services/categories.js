export const CATEGORIES = {
  food: { label: "Food & drinks", icon: "🍽️", color: "bg-orange-500", text: "text-orange-300" },
  groceries: { label: "Groceries", icon: "🛒", color: "bg-lime-500", text: "text-lime-300" },
  transport: { label: "Transport", icon: "🚕", color: "bg-sky-500", text: "text-sky-300" },
  lodging: { label: "Lodging", icon: "🏠", color: "bg-violet-500", text: "text-violet-300" },
  entertainment: { label: "Entertainment", icon: "🎟️", color: "bg-pink-500", text: "text-pink-300" },
  shopping: { label: "Shopping", icon: "🛍️", color: "bg-fuchsia-500", text: "text-fuchsia-300" },
  utilities: { label: "Utilities", icon: "💡", color: "bg-yellow-500", text: "text-yellow-300" },
  travel: { label: "Travel", icon: "✈️", color: "bg-cyan-500", text: "text-cyan-300" },
  health: { label: "Health", icon: "💊", color: "bg-emerald-500", text: "text-emerald-300" },
  other: { label: "Other", icon: "🧾", color: "bg-gray-500", text: "text-gray-300" },
};
export const cat = (key) => CATEGORIES[key] || CATEGORIES.other;
