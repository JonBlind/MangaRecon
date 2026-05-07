import { Link } from "react-router-dom";
import { useMe } from "../hooks/useMe";

export default function Landing() {
  const { data: me, isLoading } = useMe();

  return (
    <div className="space-y-10">
      <section className="rounded-3xl border border-neutral-800 bg-neutral-900 px-6 py-10 shadow-xl md:px-10 md:py-14">
        <div className="max-w-3xl space-y-5">
          <p className="text-sm font-medium uppercase tracking-wide opacity-70">
            MangaRecon
          </p>

          <h1 className="text-4xl font-semibold tracking-tight md:text-5xl">
            Find manga that fits what you already like.
          </h1>

          <p className="max-w-2xl text-lg opacity-80">
            Search manga, build collections, and generate recommendations from the titles you choose.
          </p>

          <div className="flex flex-wrap gap-3 pt-2">
            <Link
              className="rounded-xl border border-neutral-700 px-4 py-2 hover:bg-neutral-800"
              to="/search"
            >
              Browse Manga
            </Link>

            {!isLoading && me && (
              <Link
                className="rounded-xl border border-neutral-700 px-4 py-2 hover:bg-neutral-800"
                to="/collections"
              >
                View Collections
              </Link>
            )}

            {!isLoading && !me && (
              <>
                <Link
                  className="rounded-xl border border-neutral-700 px-4 py-2 hover:bg-neutral-800"
                  to="/login"
                >
                  Sign In
                </Link>

                <Link
                  className="rounded-xl border border-neutral-700 px-4 py-2 hover:bg-neutral-800"
                  to="/register"
                >
                  Create Account
                </Link>
              </>
            )}
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        <div className="rounded-2xl border border-neutral-800 bg-neutral-900 p-5">
          <h2 className="font-semibold">Search</h2>
          <p className="mt-2 text-sm opacity-75">
            Browse manga by title, genre, tag, and demographic.
          </p>
        </div>

        <div className="rounded-2xl border border-neutral-800 bg-neutral-900 p-5">
          <h2 className="font-semibold">Collect</h2>
          <p className="mt-2 text-sm opacity-75">
            Save manga into collections and organize titles around your interests.
          </p>
        </div>

        <div className="rounded-2xl border border-neutral-800 bg-neutral-900 p-5">
          <h2 className="font-semibold">Recommend</h2>
          <p className="mt-2 text-sm opacity-75">
            Generate recommendations from collections or selected manga.
          </p>
        </div>
      </section>
    </div>
  );
}