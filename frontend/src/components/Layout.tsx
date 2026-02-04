import { Link, Outlet, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { useMe } from "../hooks/useMe";
import { logout } from "../api/auth";

export default function Layout() {
  const nav = useNavigate();
  const qc = useQueryClient();
  const { data: me, isLoading } = useMe();

  async function handleLogout() {
    try {
      await logout();
    } finally {
      qc.removeQueries({ queryKey: ["me"] });
      nav("/login");
    }
  }

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100">
      <header className="border-b border-neutral-800">
        {/* Full-width header background, boxed inner content */}
        <div className="mx-auto flex max-w-6xl items-center gap-8 px-6 py-4">
          <Link to="/" className="text-lg font-semibold tracking-tight">
            MangaRecon
          </Link>

          <nav className="flex flex-1 items-center gap-6 text-sm">
            <Link to="/search" className="opacity-90 hover:opacity-100 hover:underline">
              Search
            </Link>

            {me && (
              <Link to="/collections" className="opacity-90 hover:opacity-100 hover:underline">
                Collections
              </Link>
            )}
          </nav>

          <div className="flex items-center gap-4 text-sm">
            {isLoading ? (
              <span className="opacity-70">Loading…</span>
            ) : me ? (
              <>
                <span className="max-w-[260px] truncate opacity-80">
                  {me.displayname || me.email}
                </span>
                <button
                  className="rounded-md border border-neutral-700 px-4 py-2 hover:bg-neutral-900"
                  onClick={handleLogout}
                >
                  Logout
                </button>
              </>
            ) : (
              <>
                <Link to="/login" className="opacity-90 hover:opacity-100 hover:underline">
                  Login
                </Link>
                <Link
                  to="/register"
                  className="rounded-md border border-neutral-700 px-4 py-2 hover:bg-neutral-900"
                >
                  Register
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Boxed content area */}
      <main className="mx-auto max-w-6xl px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}
