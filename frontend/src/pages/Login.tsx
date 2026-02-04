import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { login } from "../api/auth";
import { ApiRequestError } from "../api/http";

export default function Login() {
  const nav = useNavigate();
  const qc = useQueryClient();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const mutation = useMutation({
    mutationFn: () => login(email, password),
    onSuccess: async () => {
      nav("/collections", { replace: true });
      await qc.invalidateQueries({ queryKey: ["me"] });
    },
  });

  const errorMsg =
    mutation.error instanceof ApiRequestError
      ? mutation.error.message
      : mutation.error
        ? "Login failed"
        : null;

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <div className="w-full max-w-md rounded-2xl border p-6 shadow-sm">
        <h1 className="text-2xl font-semibold">Login</h1>
        <p className="mt-1 text-sm opacity-70">
          Sign in to manage collections and get recommendations.
        </p>

        <form
          className="mt-6 space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            mutation.mutate();
          }}
        >
          <div className="space-y-1">
            <label className="text-sm font-medium">Email</label>
            <input
              className="w-full rounded-xl border px-3 py-2 outline-none focus:ring"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
            />
          </div>

          <div className="space-y-1">
            <label className="text-sm font-medium">Password</label>
            <input
              className="w-full rounded-xl border px-3 py-2 outline-none focus:ring"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </div>

          {errorMsg ? (
            <div className="rounded-xl border p-3 text-sm">{errorMsg}</div>
          ) : null}

          <button
            className="w-full rounded-xl border px-3 py-2 font-medium disabled:opacity-60"
            disabled={mutation.isPending}
            type="submit"
          >
            {mutation.isPending ? "Signing in..." : "Sign in"}
          </button>

          <div className="text-sm opacity-80">
            No account?{" "}
            <Link className="underline" to="/register">
              Register
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
