import { Link } from "react-router-dom";

export default function Landing() {
  return (
    <div className="min-h-screen p-8">
      <div className="mx-auto max-w-3xl space-y-6">
        <h1 className="text-4xl font-semibold">MangaRecon</h1>
        <p className="text-lg opacity-80">
          Build collections, rate manga, and get recommendations.
        </p>

        <div className="flex gap-3">
          <Link className="rounded-xl border px-4 py-2" to="/search">
            Browse Manga
          </Link>
          <Link className="rounded-xl border px-4 py-2" to="/login">
            Sign in
          </Link>
        </div>
      </div>
    </div>
  );
}
