import { useEffect, useState } from "react";
import { api, type LinkedInProfile } from "../api";
import { Field, Spinner, StatusBadge } from "../components/ui";

export default function LinkedIn() {
  const [profile, setProfile] = useState<LinkedInProfile | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [connectLimit, setConnectLimit] = useState(20);
  const [followLimit, setFollowLimit] = useState(25);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);

  async function load() {
    const p = await api.get<LinkedInProfile>("/linkedin");
    setProfile(p);
    setUsername(p.linkedin_username || "");
    if (p.connect_daily_limit) setConnectLimit(p.connect_daily_limit);
    if (p.follow_up_daily_limit) setFollowLimit(p.follow_up_daily_limit);
  }

  useEffect(() => {
    load();
  }, []);

  if (!profile) return <Spinner />;

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setSaved(false);
    const payload: any = {
      linkedin_username: username,
      active: true,
      connect_daily_limit: connectLimit,
      follow_up_daily_limit: followLimit,
    };
    if (password) payload.linkedin_password = password;
    const updated = await api.put<LinkedInProfile>("/linkedin", payload);
    setProfile(updated);
    setPassword("");
    setSaved(true);
    setBusy(false);
  }

  return (
    <div className="mx-auto max-w-xl">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">LinkedIn account</h1>
        <StatusBadge status={profile.connection_status} />
      </div>

      {profile.connection_status === "checkpoint" && (
        <div className="card mb-4 border-red-200 bg-red-50 text-sm text-red-700">
          LinkedIn flagged a security checkpoint. Open the browser session (VNC)
          and clear the challenge, then the daemon will resume.
        </div>
      )}
      {profile.connection_status === "expired" && (
        <div className="card mb-4 border-amber-200 bg-amber-50 text-sm text-amber-700">
          Your saved session expired — the daemon will re-login on its next run.
        </div>
      )}

      <form onSubmit={save} className="card">
        <Field label="LinkedIn email">
          <input className="input" value={username} onChange={(e) => setUsername(e.target.value)} />
        </Field>
        <Field
          label="LinkedIn password"
          hint={
            profile.linkedin_password_set
              ? "A password is saved. Leave blank to keep it."
              : "Stored locally to drive the browser automation."
          }
        >
          <input
            className="input"
            type="password"
            placeholder={profile.linkedin_password_set ? "••••••••" : ""}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </Field>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Connects / day">
            <input
              className="input"
              type="number"
              value={connectLimit}
              onChange={(e) => setConnectLimit(Number(e.target.value))}
            />
          </Field>
          <Field label="Follow-ups / day">
            <input
              className="input"
              type="number"
              value={followLimit}
              onChange={(e) => setFollowLimit(Number(e.target.value))}
            />
          </Field>
        </div>
        <div className="mt-2 flex items-center gap-3">
          <button className="btn-primary" disabled={busy}>
            {busy ? "Saving…" : "Save"}
          </button>
          {saved && <span className="text-sm text-green-600">Saved</span>}
        </div>
      </form>
    </div>
  );
}
