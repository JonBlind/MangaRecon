import { useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL;

export default function MaintenancePage() {
  const [checking, setChecking] = useState(false);
  const [message, setMessage] = useState("");

  const previousPath = sessionStorage.getItem("preMaintenancePath") || "/";

  async function checkBackend() {
    setChecking(true);
    setMessage("");

    try {
      const res = await fetch(`${API_BASE}/readyz`, {
        credentials: "include",
      });

      if (!res.ok) {
        throw new Error("Still unavailable");
      }

      sessionStorage.removeItem("preMaintenancePath");
      window.location.assign(previousPath);
    } catch {
      setMessage("Service is still unavailable. Please try again shortly.");
    } finally {
      setChecking(false);
    }
  }

  useEffect(() => {
    const interval = setInterval(checkBackend, 15000);
    return () => clearInterval(interval);
  }, []);

  return (
    <main className="min-h-screen bg-black text-white flex items-center justify-center px-6">
      <section className="w-full max-w-xl rounded-2xl border border-zinc-800 bg-zinc-950 p-10 shadow-2xl text-center">
        <h1 className="text-3xl font-semibold tracking-tight mb-4">
          MangaRecon is temporarily unavailable
        </h1>

        <p className="text-zinc-300 text-base mb-8 leading-relaxed">
          We’re currently experiencing technical issues and the application has been placed in maintenance mode.
          Please try again shortly.
        </p>

        {message && (
          <p className="text-sm text-red-400 mb-4">{message}</p>
        )}

        <button
          onClick={checkBackend}
          disabled={checking}
          className="w-full rounded-lg bg-white text-black font-medium py-3 transition disabled:opacity-60"
        >
          {checking ? "Checking..." : "Try Again"}
        </button>

        <p className="mt-6 text-sm text-zinc-500">
          The page will automatically retry every 15 seconds.
        </p>
      </section>
    </main>
  );
}