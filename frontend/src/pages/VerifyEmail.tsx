import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { requestVerificationEmail, verifyEmail } from "../api/auth";
import { ApiRequestError } from "../api/http";

type VerificationStatus = "idle" | "verifying" | "success" | "error";

function verificationErrorMessage(error: unknown): string {
  if (error instanceof ApiRequestError) {
    return error.message;
  }

  return "We could not verify your email. Please try again.";
}

export default function VerifyEmail() {
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const alreadySucceeded = searchParams.get("verified") === "1";
  const linkFailed = searchParams.get("error") === "invalid";
  const navigationEmail = (location.state as { email?: string } | null)?.email;

  const [email, setEmail] = useState(navigationEmail ?? "");
  const [status, setStatus] = useState<VerificationStatus>(() => {
    if (alreadySucceeded) return "success";
    if (token) return "verifying";
    if (linkFailed) return "error";
    return "idle";
  });
  const [verificationError, setVerificationError] = useState<string | null>(
    linkFailed ? "This verification link is invalid or expired." : null,
  );
  const [resendPending, setResendPending] = useState(false);
  const [resendSent, setResendSent] = useState(false);
  const [resendError, setResendError] = useState<string | null>(null);
  const attemptedToken = useRef<string | null>(null);

  useEffect(() => {
    if (!token || attemptedToken.current === token) return;

    attemptedToken.current = token;
    setStatus("verifying");
    setVerificationError(null);

    void verifyEmail(token)
      .then(() => {
        setStatus("success");
        navigate("/verify-email?verified=1", { replace: true });
      })
      .catch((error: unknown) => {
        if (
          error instanceof ApiRequestError &&
          error.errorCode === "AUTH_ALREADY_VERIFIED"
        ) {
          setStatus("success");
          navigate("/verify-email?verified=1", { replace: true });
          return;
        }

        setStatus("error");
        setVerificationError(verificationErrorMessage(error));

        if (
          error instanceof ApiRequestError &&
          error.errorCode === "AUTH_VERIFY_INVALID"
        ) {
          navigate("/verify-email?error=invalid", { replace: true });
        }
      });
  }, [navigate, token]);

  async function resendVerification(event: React.FormEvent) {
    event.preventDefault();
    setResendError(null);
    setResendSent(false);
    setResendPending(true);

    try {
      await requestVerificationEmail(email.trim());
      setResendSent(true);
    } catch (error: unknown) {
      setResendError(
        error instanceof ApiRequestError
          ? error.message
          : "The verification email could not be sent. Please try again.",
      );
    } finally {
      setResendPending(false);
    }
  }

  if (status === "verifying") {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <div className="w-full max-w-md rounded-xl border p-6 text-center">
          <h1 className="text-2xl font-semibold">Verifying your email...</h1>
          <p className="mt-2 text-sm opacity-80">This should only take a moment.</p>
        </div>
      </div>
    );
  }

  if (status === "success") {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <div className="w-full max-w-md rounded-xl border p-6 text-center">
          <h1 className="text-2xl font-semibold">Email verified</h1>
          <p className="mt-2 text-sm opacity-80">
            Your MangaRecon account is ready to use.
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
        <h1 className="text-2xl font-semibold">
          {status === "error" ? "Verification link failed" : "Check your email"}
        </h1>

        {status === "error" ? (
          <p className="mt-2 text-sm text-red-700">{verificationError}</p>
        ) : (
          <p className="mt-2 text-sm opacity-80">
            We sent a verification link
            {navigationEmail ? (
              <>
                {" "}
                to <strong>{navigationEmail}</strong>
              </>
            ) : null}
            . Open it before signing in. The link expires after 3 days.
          </p>
        )}

        <form className="mt-6 space-y-4" onSubmit={resendVerification}>
          <div>
            <label htmlFor="verification-email" className="block text-sm mb-1">
              Email
            </label>
            <input
              id="verification-email"
              className="w-full rounded-md border px-3 py-2"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </div>

          {resendSent ? (
            <div className="rounded-md border border-green-300 bg-green-50 px-3 py-2 text-sm text-green-800">
              If that address belongs to an unverified account, a new link has been sent.
            </div>
          ) : null}

          {resendError ? (
            <div className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">
              {resendError}
            </div>
          ) : null}

          <button
            className="w-full rounded-md border px-3 py-2 font-medium disabled:opacity-50"
            type="submit"
            disabled={resendPending}
          >
            {resendPending ? "Sending..." : "Resend verification email"}
          </button>
        </form>

        <p className="mt-4 text-sm opacity-80">
          Already verified?{" "}
          <Link className="underline" to="/login">
            Log in
          </Link>
        </p>
      </div>
    </div>
  );
}
