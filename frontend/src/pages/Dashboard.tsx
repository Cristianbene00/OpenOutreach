import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Dashboard as DashData } from "../api";
import { Spinner, StatusBadge } from "../components/ui";

const FUNNEL = [
  "qualified",
  "ready_to_connect",
  "pending",
  "connected",
  "completed",
  "failed",
];

function Stat({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="card">
      <div className="text-sm text-gray-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
      {sub && <div className="text-xs text-gray-400">{sub}</div>}
    </div>
  );
}

export default function Dashboard() {
  const [data, setData] = useState<DashData | null>(null);

  useEffect(() => {
    api.get<DashData>("/dashboard").then(setData);
  }, []);

  if (!data) return <Spinner />;

  if (!data.onboarding.complete) {
    return (
      <div className="card">
        <h2 className="text-lg font-semibold">Finish setup</h2>
        <p className="mt-1 text-gray-500">
          Your control center isn't fully configured yet.
        </p>
        <Link to="/onboarding" className="btn-primary mt-4">
          Continue onboarding
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="mb-4 text-2xl font-semibold">Dashboard</h1>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <Stat
            label="Connects today"
            value={`${data.actions_today.connect} / ${data.daily_limits.connect}`}
          />
          <Stat
            label="Follow-ups today"
            value={`${data.actions_today.follow_up} / ${data.daily_limits.follow_up}`}
          />
          <Stat label="Pending approvals" value={data.pending_approvals} sub="in message queue" />
          <div className="card">
            <div className="text-sm text-gray-500">LinkedIn</div>
            <div className="mt-2">
              <StatusBadge status={data.linkedin_status} />
            </div>
          </div>
        </div>
      </div>

      <div>
        <h2 className="mb-3 text-lg font-semibold">Pipeline</h2>
        <div className="grid grid-cols-3 gap-3 md:grid-cols-6">
          {FUNNEL.map((s) => (
            <div key={s} className="card text-center">
              <div className="text-2xl font-semibold">{data.deals_by_state[s] ?? 0}</div>
              <div className="mt-1 text-xs capitalize text-gray-500">{s.replace(/_/g, " ")}</div>
            </div>
          ))}
        </div>
      </div>

      <div>
        <h2 className="mb-3 text-lg font-semibold">Campaigns</h2>
        <div className="space-y-2">
          {data.campaigns.length === 0 && (
            <p className="text-sm text-gray-500">No campaigns yet.</p>
          )}
          {data.campaigns.map((c) => (
            <Link
              key={c.id}
              to={`/campaigns/${c.id}`}
              className="card flex items-center justify-between hover:border-brand-300"
            >
              <span className="font-medium">{c.name}</span>
              <span className="flex items-center gap-2">
                {c.auto_send ? null : <span className="badge bg-amber-100 text-amber-800">review</span>}
                <span
                  className={`badge ${
                    c.enabled ? "bg-green-100 text-green-800" : "bg-gray-100 text-gray-600"
                  }`}
                >
                  {c.enabled ? "prospecting" : "stopped"}
                </span>
              </span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
