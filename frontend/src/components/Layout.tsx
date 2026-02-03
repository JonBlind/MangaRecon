import { Link, Outlet, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { useMe } from "../hooks/useMe";
import type { UserMe } from "../types/auth";
import { logout } from "../api/auth";

export default function Layout() {
  const nav = useNavigate();
  const qc = useQueryClient();
  const { data: me, isLoading } = useMe();

  async function handleLogout() {
    try {
      await logout();
    } finally {
      // hard reset auth state immediately
      qc.removeQueries({ queryKey: ["me"] });
      nav("/login");
    }
  }

  return (
    <div className="min-h-screen">
      <header className="border-b">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-4">
            <Link to="/" className="font-semibold">
              MangaRecon
            </Link>

            <nav className="flex items-center gap-3 text-sm">
              <Link to="/search" className="hover:underline">
                Search
              </Link>

              {me && (
                <>
                  <Link to="/collections" className="hover:underline">
                    Collections
                  </Link>
                </>
              )}
            </nav>
          </div>

          <div className="flex items-center gap-3 text-sm">
            {isLoading ? (
              <span className="opacity-70">…</span>
            ) : me ? (
              <>
                <span className="opacity-80">
                  {me?.displayname ?? me?.email}
                </span>
                <button
                  className="rounded-md border px-3 py-1.5 hover:bg-gray-50"
                  onClick={handleLogout}
                >
                  Logout
                </button>
              </>
            ) : (
              <>
                <Link className="hover:underline" to="/login">
                  Login
                </Link>
                <Link className="rounded-md border px-3 py-1.5 hover:bg-gray-50" to="/register">
                  Register
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
