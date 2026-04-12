import { useMemo, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { useCollectionRecommendations } from "../hooks/useRecommendations";

export default function Recommendations() {
  const [searchParams] = useSearchParams();

  const collectionId = Number(searchParams.get("collectionId"));

  const [page, setPage] = useState(1);
  const [orderBy, setOrderBy] = useState<"score" | "title" | "external_average_rating">("score");
  const [orderDir, setOrderDir] = useState<"asc" | "desc">("desc");

  const params = useMemo(
    () => ({
      page,
      size: 20,
      order_by: orderBy,
      order_dir: orderDir,
    }),
    [page, orderBy, orderDir]
  );

  const recQ = useCollectionRecommendations({
    collectionId,
    params,
    enabled: Number.isFinite(collectionId) && collectionId > 0,
  });

  if (!Number.isFinite(collectionId) || collectionId <= 0) {
    return (
      <div className="space-y-3">
        <h1 className="text-2xl font-semibold">Invalid request</h1>
        <p className="text-sm opacity-80">
          No collection specified for recommendations.
        </p>
      </div>
    );
  }

  const total = recQ.data?.total_results ?? 0;
  const size = recQ.data?.size ?? 20;
  const totalPages = Math.max(1, Math.ceil(total / size));

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold">Recommendations</h1>

      {/* Controls */}
      <div className="flex items-center gap-3">
        <select
          value={orderBy}
          onChange={(e) => setOrderBy(e.target.value as any)}
          className="rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2"
        >
          <option value="score">Score</option>
          <option value="title">Title</option>
          <option value="external_average_rating">Rating</option>
        </select>

        <select
          value={orderDir}
          onChange={(e) => setOrderDir(e.target.value as any)}
          className="rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2"
        >
          <option value="desc">Desc</option>
          <option value="asc">Asc</option>
        </select>
      </div>

      {/* Status */}
      {recQ.isLoading && (
        <div className="text-sm opacity-80">Loading recommendations…</div>
      )}

      {recQ.isError && (
        <div className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">
          {(recQ.error as any)?.message ?? "Failed to load recommendations."}
        </div>
      )}

      {/* Results */}
      {!recQ.isLoading && !recQ.isError && (
        <div className="space-y-3">
          <div className="flex items-center justify-between text-sm opacity-80">
            <span>{total.toLocaleString()} results</span>
            <span>
              Page {page} / {totalPages}
            </span>
          </div>

          <div className="grid grid-cols-1 gap-3">
            {(recQ.data?.items ?? []).map((m) => (
              <div
                key={m.manga_id}
                className="rounded-xl border border-neutral-800 bg-neutral-900 p-4"
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <Link
                      to={`/manga/${m.manga_id}`}
                      className="text-lg font-semibold hover:underline"
                    >
                      {m.title}
                    </Link>

                    {m.external_average_rating != null && (
                      <div className="text-sm opacity-60">
                        Rating: {m.external_average_rating}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Paging */}
          <div className="flex items-center gap-3 pt-2">
            <button
              className="rounded-md border border-neutral-700 px-3 py-2 disabled:opacity-50"
              disabled={page <= 1 || recQ.isFetching}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              Prev
            </button>

            <button
              className="rounded-md border border-neutral-700 px-3 py-2 disabled:opacity-50"
              disabled={page >= totalPages || recQ.isFetching}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}