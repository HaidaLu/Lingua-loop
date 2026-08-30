import { useState } from "react";
import type { FormEvent } from "react";
import { useAuth } from "../auth";

export default function Login() {
  const { registered, login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">(registered ? "login" : "register");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "register") await register(email.trim(), password);
      else await login(email.trim(), password);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-wrap">
      <form className="auth-card" onSubmit={submit}>
        <h1>Lingua Loop</h1>
        <p className="muted">
          {mode === "register"
            ? registered
              ? "An account already exists — please sign in"
              : "First run — create your account (single user)"
            : "Sign in to continue"}
        </p>

        <label>
          Email
          <input
            type="email"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>
        <label>
          Password
          <input
            type="password"
            autoComplete={mode === "register" ? "new-password" : "current-password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={6}
            required
          />
        </label>

        {error && <div className="error">{error}</div>}

        <button className="primary" type="submit" disabled={busy}>
          {busy ? "…" : mode === "register" ? "Create account" : "Sign in"}
        </button>

        {!registered && mode === "login" && (
          <button type="button" className="linkish" onClick={() => setMode("register")}>
            No account yet? Register
          </button>
        )}
        {registered && <p className="muted">Registration is closed (single-user mode).</p>}
      </form>
    </div>
  );
}
