import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { ApiError } from "../api";
import { ErrorText } from "../components/ui";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(username, password);
      navigate("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <form onSubmit={submit} className="card w-full max-w-sm">
        <h1 className="mb-1 text-xl font-semibold text-brand-700">OpenOutreach</h1>
        <p className="mb-6 text-sm text-gray-500">Sign in to your control center</p>
        <label className="label">Username</label>
        <input className="input mb-4" value={username} onChange={(e) => setUsername(e.target.value)} autoFocus />
        <label className="label">Password</label>
        <input className="input mb-2" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        <ErrorText>{error}</ErrorText>
        <button className="btn-primary mt-4 w-full" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
        <p className="mt-4 text-center text-sm text-gray-500">
          No account?{" "}
          <Link to="/signup" className="text-brand-600 hover:underline">
            Create one
          </Link>
        </p>
      </form>
    </div>
  );
}
