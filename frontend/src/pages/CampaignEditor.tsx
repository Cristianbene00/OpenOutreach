import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, ApiError, type Campaign } from "../api";
import { ErrorText, Field, Spinner } from "../components/ui";

const EMPTY: Partial<Campaign> = {
  name: "",
  campaign_objective: "",
  product_docs: "",
  booking_link: "",
  seed_public_ids: [],
  auto_send: true,
  connection_note_template: "",
  follow_up_template: "",
};

export default function CampaignEditor() {
  const { id } = useParams();
  const navigate = useNavigate();
  const isNew = !id;
  const [c, setC] = useState<Partial<Campaign> | null>(isNew ? EMPTY : null);
  const [seedText, setSeedText] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!isNew) {
      api.get<Campaign>(`/campaigns/${id}`).then((data) => {
        setC(data);
        setSeedText((data.seed_public_ids || []).join("\n"));
      });
    }
  }, [id, isNew]);

  if (!c) return <Spinner />;

  function set<K extends keyof Campaign>(k: K, v: Campaign[K]) {
    setC((prev) => ({ ...prev!, [k]: v }));
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    const payload = {
      ...c,
      seed_public_ids: seedText
        .split(/[\n,]/)
        .map((s) => s.trim())
        .filter(Boolean),
    };
    try {
      const saved = isNew
        ? await api.post<Campaign>("/campaigns", payload)
        : await api.patch<Campaign>(`/campaigns/${id}`, payload);
      navigate(`/campaigns/${saved.id}`);
      if (!isNew) {
        setC(saved);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  async function toggle() {
    const saved = await api.post<Campaign>(`/campaigns/${id}/${c!.enabled ? "stop" : "start"}`);
    setC(saved);
  }

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{isNew ? "New campaign" : c.name}</h1>
        {!isNew && (
          <button className={c.enabled ? "btn-danger" : "btn-primary"} onClick={toggle}>
            {c.enabled ? "Stop prospecting" : "Start prospecting"}
          </button>
        )}
      </div>

      <form onSubmit={save} className="space-y-6">
        <div className="card">
          <h2 className="mb-4 font-semibold">Ideal Customer Profile</h2>
          <Field label="Campaign name">
            <input className="input" value={c.name} onChange={(e) => set("name", e.target.value)} />
          </Field>
          <Field
            label="Who are you targeting?"
            hint="The AI uses this to generate LinkedIn searches and qualify leads."
          >
            <textarea
              className="input min-h-[90px]"
              value={c.campaign_objective}
              onChange={(e) => set("campaign_objective", e.target.value)}
              placeholder="e.g. Founders & heads of growth at seed-stage B2B SaaS companies in the US/EU…"
            />
          </Field>
          <Field
            label="What are you offering? (product docs)"
            hint="Context the AI uses to qualify and to write messages."
          >
            <textarea
              className="input min-h-[120px]"
              value={c.product_docs}
              onChange={(e) => set("product_docs", e.target.value)}
            />
          </Field>
          <Field label="Booking link (optional)">
            <input
              className="input"
              value={c.booking_link}
              onChange={(e) => set("booking_link", e.target.value)}
              placeholder="https://cal.com/you/intro"
            />
          </Field>
          <Field
            label="Seed profiles (optional)"
            hint="One LinkedIn URL or public id per line to kick-start discovery."
          >
            <textarea
              className="input min-h-[70px]"
              value={seedText}
              onChange={(e) => setSeedText(e.target.value)}
            />
          </Field>
        </div>

        <div className="card">
          <h2 className="mb-4 font-semibold">Messaging</h2>
          <Field
            label="First-message template"
            hint="Seeds the first message once a lead accepts. The AI personalizes it."
          >
            <textarea
              className="input min-h-[80px]"
              value={c.connection_note_template}
              onChange={(e) => set("connection_note_template", e.target.value)}
              placeholder="Hi {{first_name}}, saw you're working on… curious how you handle…"
            />
          </Field>
          <Field
            label="Follow-up template"
            hint="Guides later nudges. The AI adapts it to the conversation."
          >
            <textarea
              className="input min-h-[80px]"
              value={c.follow_up_template}
              onChange={(e) => set("follow_up_template", e.target.value)}
            />
          </Field>
          <label className="flex items-center gap-3">
            <input
              type="checkbox"
              checked={!c.auto_send}
              onChange={(e) => set("auto_send", !e.target.checked)}
            />
            <span className="text-sm">
              Review messages before sending
              <span className="block text-xs text-gray-500">
                Queue each generated message for your approval instead of auto-sending.
              </span>
            </span>
          </label>
        </div>

        <ErrorText>{error}</ErrorText>
        <div className="flex gap-3">
          <button className="btn-primary" disabled={busy}>
            {busy ? "Saving…" : "Save campaign"}
          </button>
          <button type="button" className="btn-secondary" onClick={() => navigate("/campaigns")}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
