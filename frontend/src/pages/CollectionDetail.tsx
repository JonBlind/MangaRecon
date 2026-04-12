import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  useCollection,
  useCollectionManga,
  useRemoveMangaFromCollection,
} from "../hooks/useCollections";
import type { FeedbackMessage } from "../types/ui";
export default function CollectionDetail() {
  const nav = useNavigate();
  const { id } = useParams();

  const collectionId = Number(id);
  const [page, setPage] = useState(1);
  const [confirmingMangaId, setConfirmingMangaId] = useState<number | null>(
    null
  );
  const [feedback, setFeedback] = useState<FeedbackMessage | null>(null);

  const params = useMemo(
    () => ({
      page,
      size: 20,
      order: "desc" as const,
    }),
    [page]
  );

  const collectionQ = useCollection(collectionId);
  const mangaQ = useCollectionManga(collectionId, params);
  const removeM = useRemoveMangaFromCollection(collectionId);

  const total = mangaQ.data?.total_results ?? 0;
  const size = mangaQ.data?.size ?? 20;
  const totalPages = Math.max(1, Math.ceil(total / size));

  function startRemove(mangaId: number) {
    setFeedback(null);
    setConfirmingMangaId(mangaId);
  }

  function cancelRemove() {
    setConfirmingMangaId(null);
  }

  async function confirmRemove(mangaId: number, title: string) {
    try {
      setFeedback(null);
      await removeM.mutateAsync(mangaId);

      setFeedback({
        type: "success",
        message: `"${title}" was removed from the collection.`,
      });
      setConfirmingMangaId(null);

      // if we removed the last item on a page, bump back
      const itemsOnPage = mangaQ.data?.items?.length ?? 0;
      if (page > 1 && itemsOnPage === 1) {
        setPage((p) => Math.max(1, p - 1));
      }
    } catch (err: any) {
      setFeedback({
        type: "error",
        message: err?.message ?? "Failed to remove manga.",
      });
    }
  }

  if (!Number.isFinite(collectionId) || collectionId <= 0) {
    return (
      <div className="space-y-3">
        <h1 className="text-2xl font-semibold">Invalid collection</h1>
        <button
          className="rounded-md border border-neutral-700 px-4 py-2 hover:bg-neutral-900"
          onClick={() => nav("/collections")}
        >
          Back to collections
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <button
              className="rounded-md border border-neutral-700 px-3 py-2 text-sm hover:bg-neutral-900"
              onClick={() => nav("/collections")}
            >
              ← Back
            </button>

            <h1 className="text-3xl font-semibold">
              {collectionQ.data?.collection_name ?? "Collection"}
            </h1>
          </div>

          <p className="mt-2 text-sm opacity-80">
            {collectionQ.data?.description
              ? collectionQ.data.description
              : "No description"}
          </p>
        </div>
        <button
          className="rounded-md border border-neutral-700 px-4 py-2 text-sm hover:bg-neutral-900 disabled:opacity-50"
          disabled={!collectionQ.data}
          onClick={() =>
            nav(`/recommendations?collectionId=${collectionId}`)
          }
        >
          Get Recommendations
        </button>
      </div>
      
      {collectionQ.isLoading && (
        <div className="text-sm opacity-80">Loading collection…</div>
      )}

      {collectionQ.isError && (
        <div className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">
          {(collectionQ.error as any)?.message ?? "Failed to load collection."}
        </div>
      )}

      {feedback && (
        <div
          className={`rounded-md px-3 py-2 text-sm ${
            feedback.type === "success"
              ? "border border-green-300 bg-green-50 text-green-800"
              : "border border-red-300 bg-red-50 text-red-800"
          }`}
        >
          {feedback.message}
        </div>
      )}

      <div className="space-y-3">
        <div className="flex items-center justify-between text-sm opacity-80">
          <span>
            {total.toLocaleString()} item{total === 1 ? "" : "s"}
          </span>
          <span>
            Page {page} / {totalPages}
          </span>
        </div>

        {mangaQ.isLoading && (
          <div className="text-sm opacity-80">Loading manga…</div>
        )}

        {mangaQ.isError && (
          <div className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">
            {(mangaQ.error as any)?.message ??
              "Failed to load manga in this collection."}
          </div>
        )}

        {!mangaQ.isLoading && !mangaQ.isError && (
          <div className="grid grid-cols-1 gap-3">
            {(mangaQ.data?.items ?? []).map((m) => {
              const isConfirming = confirmingMangaId === m.manga_id;
              const isRemoving = removeM.isPending && isConfirming;

              return (
                <div
                  key={m.manga_id}
                  className="rounded-xl border border-neutral-800 bg-neutral-900 p-4 transition hover:border-neutral-600"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <Link
                        to={`/manga/${m.manga_id}`}
                        className="truncate text-lg font-semibold hover:underline"
                      >
                        {m.title}
                      </Link>

                      {m.description ? (
                        <div className="mt-1 line-clamp-2 text-sm opacity-80">
                          {m.description}
                        </div>
                      ) : (
                        <div className="mt-1 text-sm opacity-60">
                          No description
                        </div>
                      )}
                    </div>

                    {!isConfirming ? (
                      <button
                        className="rounded-md border border-neutral-700 px-3 py-2 text-sm hover:bg-neutral-950 disabled:opacity-50"
                        disabled={removeM.isPending}
                        onClick={() => startRemove(m.manga_id)}
                        title="Remove from collection"
                      >
                        Remove
                      </button>
                    ) : (
                      <div className="flex shrink-0 items-center gap-2">
                        <button
                          className="rounded-md border border-neutral-700 px-3 py-2 text-sm hover:bg-neutral-950 disabled:opacity-50"
                          disabled={isRemoving}
                          onClick={cancelRemove}
                        >
                          Cancel
                        </button>

                        <button
                          className="rounded-md border border-red-700 px-3 py-2 text-sm text-red-300 hover:bg-red-950 disabled:opacity-50"
                          disabled={isRemoving}
                          onClick={() => confirmRemove(m.manga_id, m.title)}
                        >
                          {isRemoving ? "Removing…" : "Confirm remove"}
                        </button>
                      </div>
                    )}
                  </div>

                  {isConfirming && (
                    <div className="mt-3 text-sm text-neutral-300">
                      Remove <span className="font-medium">{m.title}</span> from
                      this collection?
                    </div>
                  )}
                </div>
              );
            })}

            {(mangaQ.data?.items?.length ?? 0) === 0 && (
              <div className="rounded-xl border border-neutral-800 bg-neutral-900 p-6 text-sm opacity-80">
                This collection is empty. Next we'll add "Add to collection"
                from manga pages so you can fill it quickly.
              </div>
            )}
          </div>
        )}

        <div className="flex items-center gap-3 pt-2">
          <button
            className="rounded-md border border-neutral-700 px-3 py-2 disabled:opacity-50"
            disabled={page <= 1 || mangaQ.isFetching}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            Prev
          </button>

          <button
            className="rounded-md border border-neutral-700 px-3 py-2 disabled:opacity-50"
            disabled={page >= totalPages || mangaQ.isFetching}
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}