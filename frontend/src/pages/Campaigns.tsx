import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Campaign } from "../api";
import { Spinner } from "../components/ui";

export default function Campaigns() {
  const [campaigns, setCampaigns] = useState<Campaign[] | null>(null);

  async function load() {
    setCampaigns(await api.get<Campaign[]>("/campaigns"));
  }
  useEffect(() => {
    load();
  }, []);

  async function toggle(c: Campaign) {
    await api.post(`/campaigns/${c.id}/${c.enabled ? "stop" : "start"}`);
    load();
  }

  if (!campaigns) return <Spinner />;

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Campaigns</h1>
        <Link to="/campaigns/new" className="btn-primary">
          New campaign
        </Link>
      </div>
      {campaigns.length === 0 && (
        <div className="card text-gray-500">
          No campaigns yet. Create one to define your ICP and start prospecting.
        </div>
      )}
      <div className="space-y-3">
        {campaigns.map((c) => (
          <div key={c.id} className="card flex items-center justify-between">
            <div>
              <Link to={`/campaigns/${c.id}`} className="font-medium hover:text-brand-600">
                {c.name}
              </Link>
              <div className="mt-1 line-clamp-1 max-w-md text-sm text-gray-500">
                {c.campaign_objective || "No objective set"}
              </div>
            </div>
            <div className="flex items-center gap-2">
              {!c.auto_send && (
                <span className="badge bg-amber-100 text-amber-800">review mode</span>
              )}
              <button
                className={c.enabled ? "btn-danger" : "btn-primary"}
                onClick={() => toggle(c)}
              >
                {c.enabled ? "Stop" : "Start prospecting"}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
