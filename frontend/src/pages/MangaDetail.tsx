import { useParams } from "react-router-dom";
import { useState } from "react";
import { useManga } from "../hooks/useManga";
import { useMe } from "../hooks/useMe";
import {
  useCollections,
  useAddMangaToCollection,
} from "../hooks/useCollections";

export default function MangaDetail() {
  const { id } = useParams();
  const mangaId = Number(id);

  if (!Number.isFinite(mangaId) || mangaId <= 0) {
    return <div className="p-6">Invalid manga id.</div>;
  }

  const { data, isPending, isError } = useManga(mangaId);

  // 🔹 auth + collections
  const meQ = useMe();
  const collectionsQ = useCollections({ page: 1, size: 100 });
  const [selectedCollection, setSelectedCollection] = useState<number | "">("");
  const addM = useAddMangaToCollection(
    typeof selectedCollection === "number" ? selectedCollection : -1
  );

  if (isPending) {
    return <div className="p-6">Loading…</div>;
  }

  if (isError || !data) {
    return <div className="p-6">Couldn’t load this manga.</div>;
  }

  const m = data;

  async function handleAdd() {
    if (typeof selectedCollection !== "number") return;

    try {
      await addM.mutateAsync(mangaId);
      setSelectedCollection("");
      alert("Added to collection!");
    } catch (e: any) {
      alert(e?.message ?? "Failed to add manga to collection.");
    }
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex flex-col gap-6 md:flex-row">
        <img
          src={m.cover_image_url ?? "https://placehold.co/400x600?text=No+Cover"}
          alt={m.title}
          className="w-48 h-72 object-cover rounded-xl border border-neutral-800 bg-neutral-900"
          onError={(e) => {
            e.currentTarget.src = "https://placehold.co/400x600?text=No+Cover";
          }}
        />

        <div className="space-y-3 flex-1">
          <h1 className="text-3xl font-bold">{m.title}</h1>

          {/* 🔹 Add to collection (auth-only) */}
          {!meQ.isPending && meQ.data && (
            <div className="flex items-center gap-3">
              <select
                className="rounded-md border border-neutral-700 bg-neutral-950 px-3 py-2 text-sm"
                value={selectedCollection}
                onChange={(e) =>
                  setSelectedCollection(
                    e.target.value ? Number(e.target.value) : ""
                  )
                }
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
                  typeof selectedCollection !== "number" || addM.isPending
                }
                onClick={handleAdd}
              >
                {addM.isPending ? "Adding…" : "Add"}
              </button>

              {collectionsQ.data?.items.length === 0 && (
                <span className="text-sm opacity-70">
                  You don’t have any collections yet.
                </span>
              )}
            </div>
          )}

          <div className="text-sm opacity-80 flex flex-wrap gap-x-4 gap-y-1">
            {m.published_date ? <span>Published: {m.published_date}</span> : null}
            {m.average_rating != null ? <span>Avg: {m.average_rating}</span> : null}
            {m.external_average_rating != null ? (
              <span>External: {m.external_average_rating}</span>
            ) : null}
            {m.author_id != null ? (
              <span>Author ID: {m.author_id}</span>
            ) : (
              <span>Author: Unknown</span>
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            {m.demographics.map((d) => (
              <span
                key={d.demographic_id}
                className="px-2 py-1 rounded bg-neutral-800 text-sm"
              >
                {d.demographic_name}
              </span>
            ))}

            {m.genres.map((g) => (
              <span
                key={g.genre_id}
                className="px-2 py-1 rounded bg-neutral-800 text-sm"
              >
                {g.genre_name}
              </span>
            ))}

            {m.tags.map((t) => (
              <span
                key={t.tag_id}
                className="px-2 py-1 rounded bg-neutral-800 text-sm"
              >
                {t.tag_name}
              </span>
            ))}
          </div>
        </div>
      </div>

      {m.description ? (
        <p className="leading-relaxed whitespace-pre-line">{m.description}</p>
      ) : (
        <p className="opacity-70">No description available.</p>
      )}
    </div>
  );
}
