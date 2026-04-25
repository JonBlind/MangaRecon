import { Link } from "react-router-dom";

type AuthRequiredModalProps = {
  open: boolean;
  onClose: () => void;
  title?: string;
  message?: string;
};

export default function AuthRequiredModal({
  open,
  onClose,
  title = "Sign in required",
  message = "You need an account to add manga to a collection.",
}: AuthRequiredModalProps) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-2xl border border-neutral-800 bg-neutral-950 p-5 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold">{title}</h2>
        <p className="mt-2 text-sm opacity-80">{message}</p>

        <div className="mt-6 flex flex-wrap items-center justify-end gap-2">
          <button
            type="button"
            className="rounded-md border border-neutral-700 px-3 py-2 text-sm hover:bg-neutral-900"
            onClick={onClose}
          >
            Close
          </button>

          <Link
            to="/register"
            className="rounded-md border border-neutral-700 px-3 py-2 text-sm hover:bg-neutral-900"
            onClick={onClose}
          >
            Create Account
          </Link>

          <Link
            to="/login"
            className="rounded-md border border-neutral-700 px-3 py-2 text-sm hover:bg-neutral-900"
            onClick={onClose}
          >
            Sign In
          </Link>
        </div>
      </div>
    </div>
  );
}