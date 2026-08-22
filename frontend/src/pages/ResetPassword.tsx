import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { resetPassword, validatePasswordResetToken } from "../api/auth";
import { ApiRequestError } from "../api/http";

type ResetStatus = "validating" | "ready" | "invalid" | "rate-limited" | "success";

export default function ResetPassword() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const [status, setStatus] = useState<ResetStatus>(token ? "validating" : "invalid");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setStatus("invalid");
      return;
    }

    let cancelled = false;
    setStatus("validating");

    void validatePasswordResetToken(token)
      .then(() => {
        if (!cancelled) setStatus("ready");
      })
      .catch((validationError: unknown) => {
        if (cancelled) return;

        setStatus(
          validationError instanceof ApiRequestError && validationError.statusCode === 429
            ? "rate-limited"
            : "invalid",
        );
      });

    return () => {
      cancelled = true;
    };
  }, [token]);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);

    if (!token) {
      setStatus("invalid");
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setSubmitting(true);

    try {
      await resetPassword(token, password);
      setStatus("success");
    } catch (resetError: unknown) {
      if (
        resetError instanceof ApiRequestError &&
        resetError.errorCode === "AUTH_RESET_INVALID"
      ) {
        setStatus("invalid");
      } else {
        setError(
          resetError instanceof ApiRequestError && resetError.statusCode === 429
            ? "Too many reset attempts. Please wait before trying again."
            : resetError instanceof ApiRequestError
              ? resetError.message
              : "We could not reset your password. Please try again.",
        );
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (status === "validating") {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <div className="w-full max-w-md rounded-xl border p-6 text-center">
          <h1 className="text-2xl font-semibold">Checking your reset link...</h1>
          <p className="mt-2 text-sm opacity-80">This should only take a moment.</p>
        </div>
      </div>
    );
  }

  if (status === "invalid") {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <div className="w-full max-w-md rounded-xl border p-6 text-center">
          <h1 className="text-2xl font-semibold">Reset link unavailable</h1>
          <p className="mt-2 text-sm opacity-80">
            This reset link is invalid, expired, or has already been used.
          </p>
          <Link
            className="mt-6 inline-block w-full rounded-md border px-3 py-2 font-medium"
            to="/forgot-password"
          >
            Request a new link
          </Link>
        </div>
      </div>
    );
  }

  if (status === "rate-limited") {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <div className="w-full max-w-md rounded-xl border p-6 text-center">
          <h1 className="text-2xl font-semibold">Too many reset attempts</h1>
          <p className="mt-2 text-sm opacity-80">
            Please wait a minute, then reopen your password-reset link.
          </p>
          <Link
            className="mt-6 inline-block w-full rounded-md border px-3 py-2 font-medium"
            to="/login"
          >
            Back to login
          </Link>
        </div>
      </div>
    );
  }

  if (status === "success") {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <div className="w-full max-w-md rounded-xl border p-6 text-center">
          <h1 className="text-2xl font-semibold">Password reset</h1>
          <p className="mt-2 text-sm opacity-80">
            Your password has been changed. You can now sign in.
          </p>
          <Link
            className="mt-6 inline-block w-full rounded-md border px-3 py-2 font-medium"
            to="/login"
          >
            Continue to login
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-md rounded-xl border p-6">
        <h1 className="text-2xl font-semibold">Choose a new password</h1>
        <p className="mt-2 text-sm opacity-80">Use at least 8 characters.</p>

        <form className="mt-6 space-y-4" onSubmit={onSubmit}>
          <div>
            <label htmlFor="new-password" className="block text-sm mb-1">
              New password
            </label>
            <input
              id="new-password"
              className="w-full rounded-md border px-3 py-2"
              type="password"
              minLength={8}
              autoComplete="new-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </div>

          <div>
            <label htmlFor="confirm-password" className="block text-sm mb-1">
              Confirm password
            </label>
            <input
              id="confirm-password"
              className="w-full rounded-md border px-3 py-2"
              type="password"
              minLength={8}
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
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
            {submitting ? "Resetting..." : "Reset password"}
          </button>
        </form>
      </div>
    </div>
  );
}
