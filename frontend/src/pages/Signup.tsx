import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { ApiError } from "../api";
import { ErrorText } from "../components/ui";

export default function Signup() {
  const { signup } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await signup(username, password, email);
      navigate("/onboarding");
    } catch (err) {
      if (err instanceof ApiError) {
        const d = err.data;
        const msg =
          d?.username?.[0] || d?.password?.[0] || d?.detail || "Sign up failed";
        setError(msg);
      } else {
        setError("Sign up failed");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <form onSubmit={submit} className="card w-full max-w-sm">
        <h1 className="mb-1 text-xl font-semibold text-brand-700">Create account</h1>
        <p className="mb-6 text-sm text-gray-500">Start prospecting in minutes</p>
        <label className="label">Username</label>
        <input className="input mb-4" value={username} onChange={(e) => setUsername(e.target.value)} autoFocus />
        <label className="label">Email (optional)</label>
        <input className="input mb-4" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        <label className="label">Password</label>
        <input className="input mb-2" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        <ErrorText>{error}</ErrorText>
        <button className="btn-primary mt-4 w-full" disabled={busy}>
          {busy ? "Creating…" : "Create account"}
        </button>
        <p className="mt-4 text-center text-sm text-gray-500">
          Already have an account?{" "}
          <Link to="/login" className="text-brand-600 hover:underline">
            Sign in
          </Link>
        </p>
      </form>
    </div>
  );
}
