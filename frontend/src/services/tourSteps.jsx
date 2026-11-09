/** Guided-tour content. `target` matches a data-tour="…" attribute in the UI. */
export function buildTourSteps({ showTab }) {
  return [
    {
      id: "welcome",
      icon: "👋",
      title: "Welcome to SplitSync AI",
      body: (
        <>
          Split group expenses by just <b>talking</b>. The AI does the math, finds the fewest payments, and you settle with PayPal in one tap.
          <br />
          This 60-second tour shows you around.
        </>
      ),
      before: () => showTab("overview"),
    },
    {
      id: "groups",
      target: "groups",
      title: "Your groups",
      body: "Each trip, house or event is a group. Switch between them here, or create a new one with + New.",
    },
    {
      id: "acting-as",
      target: "acting-as",
      title: "Who are you?",
      body: (
        <>
          Pick yourself here. When you type <b>“I”</b> or <b>“me”</b>, the AI knows who you mean, and balances read “You owe…”.
        </>
      ),
    },
    {
      id: "chat",
      target: "chat-input",
      title: "Just say what happened",
      body: "Type an expense in plain English. The AI figures out who paid, how much, who shares it and the category, then splits it to the cent.",
      tryIt: "I paid $60 for dinner, split between me, Alex and Sarah",
    },
    {
      id: "tools",
      target: "chat-tools",
      title: "Snap or speak it",
      body: (
        <>
          📷 <b>Scan a receipt</b>: type a note first like “Alex had the steak” to split items per person.
          <br />
          🎙️ <b>Voice</b>: tap and say the expense out loud.
        </>
      ),
    },
    {
      id: "balances",
      target: "balances",
      title: "Who owes whom",
      body: "Live net balances for everyone. Green means you're owed money, red means you owe.",
    },
    {
      id: "smart",
      target: "smart-settlement",
      title: "⚡ Smart settlement",
      body: "Instead of everyone paying everyone back, debts are simplified to the fewest possible payments.",
    },
    {
      id: "settle",
      target: "debt-actions",
      title: "Settle in one tap",
      body: (
        <>
          <b>Settle via PayPal</b> opens checkout and marks the debt paid when done.
          <br />
          <b>🔔 Nudge</b> writes a friendly (or funny!) reminder you can send on WhatsApp.
        </>
      ),
    },
    {
      id: "agent",
      target: "agent",
      title: "🤖 Settle-Up Agent",
      body: (
        <>
          Tell the agent what you want and it does the work: it plans the payments from your ledger, and after you <b>confirm</b> it creates the PayPal orders and writes reminders.
        </>
      ),
      tryIt: "Settle everything for me",
    },
    {
      id: "ledger",
      target: "ledger",
      title: "Activity ledger",
      body: "Every expense and payment, newest first. Tap a row to see the split, search, filter by category, or export to CSV.",
    },
    {
      id: "insights",
      target: "insights",
      title: "📊 Insights & AI copilot",
      body: "See where the money went, who's carrying the group, and ask questions in plain English.",
      tryIt: "How much did we spend on food?",
      before: () => showTab("insights"),
    },
    {
      id: "live",
      target: "live",
      title: "🔴 Live sync",
      body: "Open the app on your friends' phones. New expenses and payments appear on every device instantly.",
      before: () => showTab("overview"),
    },
    {
      id: "status",
      target: "status",
      title: "AI & PayPal status",
      body: "Shows which AI model (Groq or Gemini) and whether PayPal Sandbox are connected. Without keys the app still works in offline / demo mode.",
    },
    {
      id: "done",
      icon: "🎉",
      title: "You're all set!",
      body: (
        <>
          Try logging your first expense now. You can replay this tour anytime from <b>❔ Tour</b> in the top bar.
        </>
      ),
    },
  ];
}
