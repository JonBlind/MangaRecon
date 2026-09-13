import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { useMe } from "../hooks/useMe";
import { logout } from "../api/auth";

export default function Layout() {
  const nav = useNavigate();
  const location = useLocation();
  const qc = useQueryClient();
  const pageLoadsPrimaryPublicData =
    location.pathname === "/search" ||
    location.pathname === "/search/" ||
    location.pathname.startsWith("/manga/");
  const { data: me, isLoading, isPending } = useMe(!pageLoadsPrimaryPublicData);

  const isCheckingAuth =
    me === undefined && (isLoading || (pageLoadsPrimaryPublicData && isPending));

  async function handleLogout() {
    try {
      await logout();
    } finally {
      qc.clear();
      nav("/login");
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-neutral-950 text-neutral-100">
      <header className="border-b border-neutral-800">
        <div className="mx-auto flex max-w-6xl items-center gap-8 px-6 py-4">
          <Link to="/" className="text-lg font-semibold tracking-tight">
            MangaRecon
          </Link>

          <nav className="flex flex-1 items-center gap-6 text-sm">
            <Link to="/search" className="opacity-90 hover:opacity-100 hover:underline">
              Search
            </Link>

            {me && (
              <Link
                to="/collections"
                className="opacity-90 hover:opacity-100 hover:underline"
              >
                Collections
              </Link>
            )}
          </nav>

          <div className="flex items-center gap-4 text-sm">
            {me ? (
              <>
                <Link
                  to="/account"
                  className="max-w-[260px] truncate opacity-80 hover:underline"
                >
                  {me.displayname}
                </Link>
                <button
                  className="rounded-md border border-neutral-700 px-4 py-2 hover:bg-neutral-900"
                  onClick={handleLogout}
                >
                  Logout
                </button>
              </>
            ) : isCheckingAuth ? (
              <span className="opacity-70">Loading…</span>
            ) : (
              <>
                <Link
                  to="/login"
                  className="opacity-90 hover:opacity-100 hover:underline"
                >
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

      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">
        <Outlet />
      </main>

      <footer className="border-t border-neutral-800 bg-neutral-900/30 text-neutral-400">
        <div className="mx-auto max-w-6xl px-6 py-8">
          <div className="grid gap-8 md:grid-cols-3">
            <div className="space-y-2">
              <Link
                to="/"
                className="inline-block font-semibold text-neutral-100 hover:text-white"
              >
                MangaRecon
              </Link>
              <p className="max-w-sm text-sm leading-6">
                Discover manga, organize your collections, and find personalized
                recommendations.
              </p>
            </div>

            <div className="space-y-2">
              <h2 className="text-sm font-semibold text-neutral-200">Support</h2>
              <a
                href="mailto:support@mangarecon.com"
                className="text-sm underline underline-offset-4 hover:text-neutral-200"
              >
                support@mangarecon.com
              </a>
            </div>

            <div className="space-y-2">
              <h2 className="text-sm font-semibold text-neutral-200">Data source</h2>
              <p className="text-sm leading-6">
                Catalog data provided by{" "}
                <a
                  href="https://www.mangaupdates.com/"
                  target="_blank"
                  rel="noreferrer"
                  className="underline underline-offset-4 hover:text-neutral-200"
                >
                  MangaUpdates
                </a>
                .
              </p>
            </div>
          </div>

          <div className="mt-8 flex flex-col gap-2 border-t border-neutral-800 pt-4 text-xs sm:flex-row sm:items-center sm:justify-between">
            <p>© {new Date().getFullYear()} MangaRecon</p>
            <p>
              Cover artwork belongs to its respective rights holders. MangaRecon is
              not affiliated with MangaUpdates.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
