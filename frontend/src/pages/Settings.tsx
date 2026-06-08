import { useEffect, useState } from "react";
import { api, type LLMSettings } from "../api";
import { Field, Spinner } from "../components/ui";

const PROVIDERS = [
  "openai",
  "anthropic",
  "google",
  "groq",
  "mistral",
  "cohere",
  "openai_compatible",
];

export default function Settings() {
  const [cfg, setCfg] = useState<LLMSettings | null>(null);
  const [key, setKey] = useState("");
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get<LLMSettings>("/settings/llm").then(setCfg);
  }, []);

  if (!cfg) return <Spinner />;

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setSaved(false);
    const payload: any = {
      llm_provider: cfg!.llm_provider,
      ai_model: cfg!.ai_model,
      llm_api_base: cfg!.llm_api_base,
    };
    if (key) payload.llm_api_key = key;
    const updated = await api.put<LLMSettings>("/settings/llm", payload);
    setCfg(updated);
    setKey("");
    setSaved(true);
    setBusy(false);
  }

  return (
    <div className="mx-auto max-w-xl">
      <h1 className="mb-6 text-2xl font-semibold">AI model settings</h1>
      <form onSubmit={save} className="card">
        <Field label="Provider">
          <select
            className="input"
            value={cfg.llm_provider}
            onChange={(e) => setCfg({ ...cfg, llm_provider: e.target.value })}
          >
            {PROVIDERS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Model" hint="e.g. gpt-4o, claude-sonnet-4-6, gemini-2.0-flash">
          <input
            className="input"
            value={cfg.ai_model}
            onChange={(e) => setCfg({ ...cfg, ai_model: e.target.value })}
          />
        </Field>
        <Field
          label="API key"
          hint={cfg.llm_api_key_set ? "A key is saved. Leave blank to keep it." : "Required."}
        >
          <input
            className="input"
            type="password"
            placeholder={cfg.llm_api_key_set ? "••••••••" : "sk-…"}
            value={key}
            onChange={(e) => setKey(e.target.value)}
          />
        </Field>
        {cfg.llm_provider === "openai_compatible" && (
          <Field label="API base URL">
            <input
              className="input"
              value={cfg.llm_api_base}
              onChange={(e) => setCfg({ ...cfg, llm_api_base: e.target.value })}
            />
          </Field>
        )}
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
