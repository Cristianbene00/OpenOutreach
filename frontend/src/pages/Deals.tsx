import { useEffect, useState } from "react";
import { api, type ChatMsg, type Deal } from "../api";
import { Spinner, StatusBadge } from "../components/ui";

function Conversation({ deal, onClose }: { deal: Deal; onClose: () => void }) {
  const [msgs, setMsgs] = useState<ChatMsg[] | null>(null);
  useEffect(() => {
    api.get<ChatMsg[]>(`/deals/${deal.id}/messages`).then(setMsgs);
  }, [deal.id]);

  return (
    <div className="fixed inset-0 z-20 flex">
      <div className="flex-1 bg-black/30" onClick={onClose} />
      <div className="flex h-full w-full max-w-md flex-col border-l border-gray-200 bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-gray-200 p-4">
          <div>
            <div className="font-medium">{deal.public_identifier}</div>
            <a href={deal.linkedin_url} target="_blank" className="text-xs text-brand-600 hover:underline">
              View on LinkedIn
            </a>
          </div>
          <button className="btn-secondary" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="flex-1 space-y-3 overflow-y-auto p-4">
          {!msgs ? (
            <Spinner />
          ) : msgs.length === 0 ? (
            <p className="text-sm text-gray-500">No messages yet.</p>
          ) : (
            msgs.map((m) => (
              <div
                key={m.id}
                className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                  m.is_outgoing
                    ? "ml-auto bg-brand-600 text-white"
                    : "bg-gray-100 text-gray-800"
                }`}
              >
                {m.content}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

export default function Deals() {
  const [deals, setDeals] = useState<Deal[] | null>(null);
  const [active, setActive] = useState<Deal | null>(null);

  useEffect(() => {
    api.get<Deal[]>("/deals").then(setDeals);
  }, []);

  if (!deals) return <Spinner />;

  return (
    <div>
      <h1 className="mb-6 text-2xl font-semibold">Deals</h1>
      {deals.length === 0 ? (
        <div className="card text-gray-500">
          No deals yet. They appear as the daemon discovers and contacts leads.
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs uppercase text-gray-500">
              <tr>
                <th className="px-4 py-2">Lead</th>
                <th className="px-4 py-2">Campaign</th>
                <th className="px-4 py-2">State</th>
                <th className="px-4 py-2">Outcome</th>
                <th className="px-4 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {deals.map((d) => (
                <tr key={d.id} className="border-t border-gray-100 hover:bg-gray-50">
                  <td className="px-4 py-2 font-medium">{d.public_identifier}</td>
                  <td className="px-4 py-2 text-gray-500">{d.campaign_name}</td>
                  <td className="px-4 py-2">
                    <StatusBadge status={d.state} />
                  </td>
                  <td className="px-4 py-2 text-gray-500">{d.outcome || "—"}</td>
                  <td className="px-4 py-2 text-right">
                    <button className="text-brand-600 hover:underline" onClick={() => setActive(d)}>
                      Conversation
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {active && <Conversation deal={active} onClose={() => setActive(null)} />}
    </div>
  );
}
