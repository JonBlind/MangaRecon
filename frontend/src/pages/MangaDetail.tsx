import { Link, useLocation, useParams } from "react-router-dom";
import { useEffect, useState } from "react";
import { useManga } from "../hooks/useManga";
import { useMe } from "../hooks/useMe";
import {
  useCollections,
  useAddMangaToCollection,
} from "../hooks/useCollections";

const FALLBACK_COVER = "https://placehold.co/400x600?text=No+Cover";

type MangaDetailLocationState = {
  returnTo?: string;
};

type FeedbackState = {
  type: "success" | "error";
  message: string;
} | null;

export default function MangaDetail() {
  const { id } = useParams();
  const location = useLocation();
  const state = location.state as MangaDetailLocationState | null;
  const backTo = state?.returnTo || "/search";

  const mangaId = Number(id);

  if (!Number.isFinite(mangaId) || mangaId <= 0) {
    return <div className="p-6">Invalid manga id.</div>;
  }

  const { data, isPending, isError } = useManga(mangaId);

  // auth + collections
  const meQ = useMe();
  const collectionsQ = useCollections({ page: 1, size: 100 });
  const [selectedCollection, setSelectedCollection] = useState<number | "">("");
  const [feedback, setFeedback] = useState<FeedbackState>(null);
  const addM = useAddMangaToCollection(typeof selectedCollection === "number" ? selectedCollection : -1);

  useEffect(() => {
    setFeedback(null);
  }, [mangaId]);

  if (isPending) {
    return <div className="p-6">Loading manga…</div>;
  }

  if (isError || !data) {
    return <div className="p-6">Couldn't load this manga.</div>;
  }

  const m = data;
  const demographics = m.demographics ?? [];
  const genres = m.genres ?? [];
  const tags = m.tags ?? [];

  async function handleAdd() {
    if (typeof selectedCollection !== "number") return;

    setFeedback(null);

    try {
      await addM.mutateAsync(mangaId);
      setSelectedCollection("");
      setFeedback({
        type: "success",
        message: "Manga added to collection.",
      });
    } catch (e: any) {
      setFeedback({
        type: "error",
        message: e?.message ?? "Failed to add manga to collection.",
      });
    }
  }

  return (
    <div className="space-y-6 p-6">
      <div>
        <Link
          to={backTo}
          className="text-sm text-neutral-400 hover:text-neutral-200"
        >
          ← Back to results
        </Link>
      </div>

      <div className="flex flex-col gap-6 md:flex-row">
        <img
          src={m.cover_image_url ?? FALLBACK_COVER}
          alt={m.title}
          className="h-72 w-48 rounded-xl border border-neutral-800 bg-neutral-900 object-cover"
          onError={(e) => {
            e.currentTarget.src = FALLBACK_COVER;
          }}
        />

        <div className="flex-1 space-y-4">
          <h1 className="text-3xl font-bold">{m.title}</h1>

          {!meQ.isPending && meQ.data && (
            <div className="space-y-3">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                <select
                  className="rounded-md border border-neutral-700 bg-neutral-950 px-3 py-2 text-sm"
                  value={selectedCollection}
                  onChange={(e) => {
                    setFeedback(null);
                    setSelectedCollection(
                      e.target.value ? Number(e.target.value) : ""
                    );
                  }}
                  disabled={collectionsQ.isLoading || addM.isPending}
                >
                  <option value="">Add to collection…</option>
                  {(collectionsQ.data?.items ?? []).map((c) => (
                    <option key={c.collection_id} value={c.collection_id}>
                      {c.collection_name}
                    </option>
                  ))}
                </select>

                <button
                  className="rounded-md border border-neutral-700 px-3 py-2 text-sm hover:bg-neutral-900 disabled:opacity-50"
                  disabled={
                    typeof selectedCollection !== "number" ||
                    addM.isPending ||
                    collectionsQ.isLoading
                  }
                  onClick={handleAdd}
                >
                  {addM.isPending ? "Adding…" : "Add"}
                </button>
              </div>

              {collectionsQ.isLoading && (
                <p className="text-sm opacity-70">Loading collections…</p>
              )}

              {!collectionsQ.isLoading &&
                (collectionsQ.data?.items?.length ?? 0) === 0 && (
                  <p className="text-sm opacity-70">
                    You don't have any collections yet.
                  </p>
                )}

              {feedback && (
                <p
                  className={
                    feedback.type === "success"
                      ? "text-sm text-green-400"
                      : "text-sm text-red-400"
                  }
                >
                  {feedback.message}
                </p>
              )}
            </div>
          )}

          <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm opacity-80">
            {m.published_date ? <span>Published: {m.published_date}</span> : null}
            {m.average_rating != null ? <span>Avg: {m.average_rating}</span> : null}
            {m.external_average_rating != null ? (
              <span>External: {m.external_average_rating}</span>
            ) : null}
          </div>

          {(demographics.length > 0 || genres.length > 0 || tags.length > 0) && (
            <div className="flex flex-wrap gap-2">
              {demographics.map((d) => (
                <span
                  key={d.demographic_id}
                  className="rounded bg-neutral-800 px-2 py-1 text-sm"
                >
                  {d.demographic_name}
                </span>
              ))}

              {genres.map((g) => (
                <span
                  key={g.genre_id}
                  className="rounded bg-neutral-800 px-2 py-1 text-sm"
                >
                  {g.genre_name}
                </span>
              ))}

              {tags.map((t) => (
                <span
                  key={t.tag_id}
                  className="rounded bg-neutral-800 px-2 py-1 text-sm"
                >
                  {t.tag_name}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {m.description ? (
        <p className="whitespace-pre-line leading-relaxed">{m.description}</p>
      ) : (
        <p className="opacity-70">No description available.</p>
      )}
    </div>
  );
}