import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { register } from "../api/auth";

export default function Register() {
  const nav = useNavigate();

  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [displayname, setDisplayname] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {

      if (password !== confirmPassword) {
        setError("Passwords do not match.");
        setSubmitting(false);
        return;
      }

      await register({ email, password, username, displayname });
      nav("/login");
    } 

    catch (err: any) {
      const raw = err?.message ?? "Registration failed.";
      const pretty =
        raw === "REGISTER_USER_ALREADY_EXISTS"
          ? "An account with that email already exists."
          : raw;

      setError(pretty);
    }
     
    finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-md rounded-xl border p-6">
        <h1 className="text-2xl font-semibold">Create account</h1>
        <p className="mt-1 text-sm opacity-80">
          Already have an account?{" "}
          <Link className="underline" to="/login">
            Log in
          </Link>
        </p>

        <form className="mt-6 space-y-4" onSubmit={onSubmit}>
          <div>
            <label className="block text-sm mb-1">Email</label>
            <input
              className="w-full rounded-md border px-3 py-2"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div>
            <label className="block text-sm mb-1">Username</label>
            <input
              className="w-full rounded-md border px-3 py-2"
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </div>

          <div>
            <label className="block text-sm mb-1">Display name</label>
            <input
              className="w-full rounded-md border px-3 py-2"
              type="text"
              value={displayname}
              onChange={(e) => setDisplayname(e.target.value)}
              required
            />
          </div>

          <div>
            <label className="block text-sm mb-1">Password (Min. 8 Characters)</label>
            <input
              className="w-full rounded-md border px-3 py-2"
              type="password"
              minLength={8}
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="block text-sm mb-1">Confirm password</label>
            <input
              className="w-full rounded-md border px-3 py-2"
              type="password"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
            />
          </div>

          {error && (
            <div className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">
              {error}
            </div>
          )}

          <button
            className="w-full rounded-md border px-3 py-2 font-medium disabled:opacity-50"
            type="submit"
            disabled={submitting}
          >
            {submitting ? "Creating..." : "Create account"}
          </button>
        </form>
      </div>
    </div>
  );
}