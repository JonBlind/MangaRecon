import { useMemo } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { useCollectionRecommendations, useQueryListRecommendations } from "../hooks/useRecommendations";
import type { RecommendationPage } from "../types/recommendation";
import MangaCard from "../components/MangaCard";

export default function Recommendations() {
  const nav = useNavigate();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();

  const collectionId = Number(searchParams.get("collectionId") ?? "0");

  const mangaIds = location.state?.mangaIds ?? [];

  const isQueryListMode = mangaIds.length > 0;

  const params = useMemo(
    () => ({
      page: Number(searchParams.get("page") ?? "1"),
      size: 25,
      order_by: (searchParams.get("order_by") as any) ?? "score",
      order_dir: (searchParams.get("order_dir") as any) ?? "desc",
    }),
    [searchParams]
  );

  function updateParams(updates: Record<string, string | number | null | undefined>) {
    const next = new URLSearchParams(searchParams);

    for (const [key, value] of Object.entries(updates)) {
      if (value === null || value === undefined || value === "") {
        next.delete(key);
      } else {
        next.set(key, String(value));
      }
    }

    setSearchParams(next);
  }

  const collectionQuery = useCollectionRecommendations({
    collectionId,
    params,
    enabled: !isQueryListMode && !!collectionId,
  });

  const queryListQuery = useQueryListRecommendations({
    payload: { manga_ids: mangaIds },
    params,
    enabled: isQueryListMode,
  });

  const activeQuery = isQueryListMode ? queryListQuery : collectionQuery;

  const data: RecommendationPage | undefined = activeQuery.data;

  const total = data?.total_results ?? 0;
  const size = data?.size ?? 25;
  const page = data?.page ?? 1;
  const totalPages = Math.max(1, Math.ceil(total / size));

  return (
    <div className="space-y-6">

      <div>
        <button
          onClick={() => nav(-1)}
          className="text-sm opacity-80 hover:underline"
        >
          ← Back
        </button>

        <h1 className="text-3xl font-semibold mt-2">Recommendations</h1>

        <p className="text-sm opacity-80 mt-1">
          {isQueryListMode
            ? "Based on selected manga"
            : "Based on collection"}
        </p>
      </div>

      {activeQuery.isLoading && (
        <div className="text-sm opacity-80">Loading recommendations…</div>
      )}

      {activeQuery.isError && (
        <div className="text-sm text-red-400">
          Failed to load recommendations.
        </div>
      )}

      <div className="space-y-2">

        <div className="flex items-center justify-between text-sm opacity-80">
          <span>
            {total.toLocaleString()} result{total === 1 ? "" : "s"}
          </span>
          <span>
            Page {page} / {totalPages}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
          {(data?.items ?? []).map((manga) => (
            <MangaCard
              key={manga.manga_id}
              manga={manga}
            />
          ))}
        </div>

        {!activeQuery.isLoading && (data?.items?.length ?? 0) === 0 && (
          <div className="text-sm opacity-80">No results.</div>
        )}
      </div>

      <div className="flex items-center gap-3">
        <button
          className="rounded-md border border-neutral-700 px-3 py-2 disabled:opacity-50"
          disabled={page <= 1 || activeQuery.isFetching}
          onClick={() => updateParams({ page: Math.max(1, page - 1) })}
        >
          Prev
        </button>

        <button
          className="rounded-md border border-neutral-700 px-3 py-2 disabled:opacity-50"
          disabled={page >= totalPages || activeQuery.isFetching}
          onClick={() => updateParams({ page: Math.min(totalPages, page + 1) })}
        >
          Next
        </button>
      </div>
    </div>
  );
}