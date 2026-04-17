import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { LayoutGrid, List } from "lucide-react";
import MangaCard from "../components/MangaCard";
import { useCollection } from "../hooks/useCollections";
import { useCollectionRecommendations } from "../hooks/useRecommendations";
import type { MangaListItem } from "../types/manga";

type ViewMode = "tiles" | "list";

const FALLBACK_COVER = "https://placehold.co/400x600?text=No+Cover";

export default function Recommendations() {
  const nav = useNavigate();
  const [searchParams] = useSearchParams();

  const collectionId = Number(searchParams.get("collectionId"));

  const [page, setPage] = useState(1);
  const [viewMode, setViewMode] = useState<ViewMode>("tiles");
  const [orderBy, setOrderBy] = useState<
    "score" | "title" | "external_average_rating"
  >("score");
  const [orderDir, setOrderDir] = useState<"asc" | "desc">("desc");

  useEffect(() => {
    setPage(1);
  }, [orderBy, orderDir]);

  const params = useMemo(
    () => ({
      page,
      size: 20,
      order_by: orderBy,
      order_dir: orderDir,
    }),
    [page, orderBy, orderDir]
  );

  const collectionQ = useCollection(collectionId);

  const recQ = useCollectionRecommendations({
    collectionId,
    params,
    enabled: Number.isFinite(collectionId) && collectionId > 0,
  });

  const cardItems: MangaListItem[] = useMemo(
    () =>
      (recQ.data?.items ?? []).map((m) => ({
        manga_id: m.manga_id,
        title: m.title,
        cover_image_url: m.cover_image_url ?? null,
        external_average_rating: m.external_average_rating ?? null,
      })),
    [recQ.data]
  );

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
      <div className="space-y-4">
        <button
          className="w-fit text-sm text-neutral-400 transition hover:text-white"
          onClick={() => nav(`/collections/${collectionId}`)}
        >
          ← Back to Collection
        </button>

        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-1">
            <h1 className="text-3xl font-semibold">Recommendations</h1>
            <p className="text-sm opacity-75">
              Recommendations based on{" "}
              <span className="font-medium">
                {collectionQ.data?.collection_name ?? "this collection"}
              </span>
              .
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <label className="text-sm opacity-70">Sort by</label>

            <select
              value={orderBy}
              onChange={(e) =>
                setOrderBy(
                  e.target.value as "score" | "title" | "external_average_rating"
                )
              }
              className="rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2"
            >
              <option value="score">Best Match</option>
              <option value="title">Title</option>
              <option value="external_average_rating">Rating</option>
            </select>

            <select
              value={orderDir}
              onChange={(e) => setOrderDir(e.target.value as "asc" | "desc")}
              className="rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2"
            >
              <option value="desc">Descending</option>
              <option value="asc">Ascending</option>
            </select>

            <div className="flex items-center overflow-hidden rounded-md border border-neutral-700">
              <button
                type="button"
                aria-label="Tile view"
                title="Tile view"
                className={`flex items-center justify-center px-3 py-2 transition ${
                  viewMode === "tiles"
                    ? "bg-neutral-800 text-white"
                    : "bg-neutral-900 text-neutral-400 hover:bg-neutral-800 hover:text-white"
                }`}
                onClick={() => setViewMode("tiles")}
              >
                <LayoutGrid className="h-4 w-4" />
              </button>

              <button
                type="button"
                aria-label="List view"
                title="List view"
                className={`flex items-center justify-center border-l border-neutral-700 px-3 py-2 transition ${
                  viewMode === "list"
                    ? "bg-neutral-800 text-white"
                    : "bg-neutral-900 text-neutral-400 hover:bg-neutral-800 hover:text-white"
                }`}
                onClick={() => setViewMode("list")}
              >
                <List className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {recQ.data?.seed_truncated && (
        <div className="rounded-md border border-yellow-700 bg-yellow-900/30 px-3 py-2 text-sm text-yellow-200">
          Large collection detected — recommendations were generated using a
          subset of items.
        </div>
      )}

      {recQ.isLoading && (
        <div className="text-sm opacity-80">Loading recommendations…</div>
      )}

      {recQ.isError && (
        <div className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">
          {(recQ.error as any)?.message ?? "Failed to load recommendations."}
        </div>
      )}

      {!recQ.isLoading && !recQ.isError && (
        <div className="space-y-3">
          <div className="flex items-center justify-between text-sm opacity-80">
            <span>{total.toLocaleString()} results</span>
            <span>
              Page {page} / {totalPages}
            </span>
          </div>

          {cardItems.length === 0 ? (
            <div className="rounded-xl border border-neutral-800 bg-neutral-900 p-6 text-sm opacity-80">
              No recommendations were found for this collection.
            </div>
          ) : viewMode === "tiles" ? (
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
              {cardItems.map((manga) => (
                <MangaCard key={manga.manga_id} manga={manga} />
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3">
              {(recQ.data?.items ?? []).map((m) => (
                <div
                  key={m.manga_id}
                  className="rounded-xl border border-neutral-800 bg-neutral-900 p-4 transition hover:border-neutral-600"
                >
                  <div className="flex items-start gap-4">
                    <Link
                      to={`/manga/${m.manga_id}`}
                      className="h-24 w-16 shrink-0 overflow-hidden rounded-md border border-neutral-800 bg-neutral-950"
                    >
                      <img
                        src={m.cover_image_url || FALLBACK_COVER}
                        alt={m.title}
                        className="h-full w-full object-cover"
                      />
                    </Link>

                    <div className="min-w-0 flex-1">
                      <Link
                        to={`/manga/${m.manga_id}`}
                        className="line-clamp-2 text-lg font-semibold hover:underline"
                      >
                        {m.title}
                      </Link>

                      {m.external_average_rating != null && (
                        <div className="mt-2 text-sm opacity-60">
                          Rating: {m.external_average_rating}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

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