import { useEffect, useState } from "react";
import { api, type QueueMessage } from "../api";
import { Spinner, StatusBadge } from "../components/ui";

const TABS = [
  { key: "pending_approval", label: "Pending" },
  { key: "approved", label: "Approved" },
  { key: "sent", label: "Sent" },
  { key: "rejected", label: "Rejected" },
];

export default function Queue() {
  const [tab, setTab] = useState("pending_approval");
  const [items, setItems] = useState<QueueMessage[] | null>(null);
  const [edits, setEdits] = useState<Record<number, string>>({});

  async function load() {
    setItems(await api.get<QueueMessage[]>(`/queue?status=${tab}`));
  }
  useEffect(() => {
    setItems(null);
    load();
  }, [tab]);

  async function approve(m: QueueMessage) {
    await api.post(`/queue/${m.id}/approve`, { body: edits[m.id] ?? m.body });
    load();
  }
  async function reject(m: QueueMessage) {
    await api.post(`/queue/${m.id}/reject`);
    load();
  }

  return (
    <div>
      <h1 className="mb-6 text-2xl font-semibold">Message queue</h1>
      <div className="mb-4 flex gap-1 border-b border-gray-200">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium ${
              tab === t.key
                ? "border-brand-600 text-brand-700"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {!items ? (
        <Spinner />
      ) : items.length === 0 ? (
        <div className="card text-gray-500">Nothing here.</div>
      ) : (
        <div className="space-y-3">
          {items.map((m) => (
            <div key={m.id} className="card">
              <div className="mb-2 flex items-center justify-between">
                <div className="text-sm">
                  <span className="font-medium">{m.lead_name}</span>
                  <span className="text-gray-400"> · {m.campaign_name} · {m.kind.replace(/_/g, " ")}</span>
                </div>
                <StatusBadge status={m.status} />
              </div>
              {tab === "pending_approval" ? (
                <textarea
                  className="input min-h-[70px]"
                  defaultValue={m.body}
                  onChange={(e) => setEdits({ ...edits, [m.id]: e.target.value })}
                />
              ) : (
                <p className="whitespace-pre-wrap text-sm text-gray-700">{m.body}</p>
              )}
              {tab === "pending_approval" && (
                <div className="mt-3 flex gap-2">
                  <button className="btn-primary" onClick={() => approve(m)}>
                    Approve & send
                  </button>
                  <button className="btn-secondary" onClick={() => reject(m)}>
                    Reject
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
