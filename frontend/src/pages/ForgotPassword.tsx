import { useState } from "react";
import { Link } from "react-router-dom";

import { requestPasswordReset } from "../api/auth";
import { ApiRequestError } from "../api/http";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      await requestPasswordReset(email.trim());
      setSubmitted(true);
    } catch (requestError: unknown) {
      setError(
        requestError instanceof ApiRequestError && requestError.statusCode === 429
          ? "Too many reset requests. Please wait before trying again."
          : "We could not submit your request. Please try again.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-md rounded-xl border p-6">
        <h1 className="text-2xl font-semibold">Reset your password</h1>
        <p className="mt-2 text-sm opacity-80">
          Enter your email address and we will send you a reset link.
        </p>

        {submitted ? (
          <div className="mt-6 space-y-4">
            <div className="rounded-md border border-green-300 bg-green-50 px-3 py-2 text-sm text-green-800">
              If that address belongs to an account, a password-reset link has been sent.
            </div>
            <Link
              className="inline-block w-full rounded-md border px-3 py-2 text-center font-medium"
              to="/login"
            >
              Back to login
            </Link>
          </div>
        ) : (
          <form className="mt-6 space-y-4" onSubmit={onSubmit}>
            <div>
              <label htmlFor="reset-email" className="block text-sm mb-1">
                Email
              </label>
              <input
                id="reset-email"
                className="w-full rounded-md border px-3 py-2"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            </div>

            {error ? (
              <div className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">
                {error}
              </div>
            ) : null}

            <button
              className="w-full rounded-md border px-3 py-2 font-medium disabled:opacity-50"
              type="submit"
              disabled={submitting}
            >
              {submitting ? "Sending..." : "Send reset link"}
            </button>

            <p className="text-sm opacity-80">
              Remembered your password?{" "}
              <Link className="underline" to="/login">
                Log in
              </Link>
            </p>
          </form>
        )}
      </div>
    </div>
  );
}
