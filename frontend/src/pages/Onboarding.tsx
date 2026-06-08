import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { Spinner } from "../components/ui";

function Step({
  done,
  title,
  desc,
  to,
  cta,
}: {
  done: boolean;
  title: string;
  desc: string;
  to: string;
  cta: string;
}) {
  return (
    <div className="card flex items-center justify-between">
      <div className="flex items-center gap-4">
        <div
          className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-bold ${
            done ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-400"
          }`}
        >
          {done ? "✓" : "•"}
        </div>
        <div>
          <div className="font-medium">{title}</div>
          <div className="text-sm text-gray-500">{desc}</div>
        </div>
      </div>
      <Link to={to} className={done ? "btn-secondary" : "btn-primary"}>
        {done ? "Edit" : cta}
      </Link>
    </div>
  );
}

export default function Onboarding() {
  const { me, loading } = useAuth();
  const navigate = useNavigate();
  if (loading || !me) return <Spinner />;
  const o = me.onboarding;

  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="mb-1 text-2xl font-semibold">Welcome, {me.user.username}</h1>
      <p className="mb-8 text-gray-500">
        Finish these steps to start prospecting on autopilot.
      </p>
      <div className="space-y-3">
        <Step
          done={o.llm_configured}
          title="1. Connect an AI model"
          desc="Add your LLM provider + API key — the brain that qualifies leads and writes messages."
          to="/settings"
          cta="Add API key"
        />
        <Step
          done={o.linkedin_configured}
          title="2. Connect LinkedIn"
          desc="Add the LinkedIn account the automation will run as."
          to="/linkedin"
          cta="Connect"
        />
        <Step
          done={o.has_campaign}
          title="3. Define your ICP"
          desc="Describe who you want to reach and what you're offering."
          to="/campaigns/new"
          cta="Create campaign"
        />
      </div>
      <button
        className="btn-primary mt-8 w-full"
        disabled={!o.complete}
        onClick={() => navigate("/")}
      >
        {o.complete ? "Go to dashboard" : "Complete all steps to continue"}
      </button>
    </div>
  );
}
