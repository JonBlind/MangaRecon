import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getDemographics, getGenres, getTags } from "../api/metadata";
import { searchMangas } from "../api/manga";
import { keepPreviousData } from "@tanstack/react-query";
import type { MangaSearchResponse } from "../types/manga";
import MangaCard from "../components/MangaCard";
import type { MangaCardManga } from "../types/mangacard";

export default function Search() {
  const [title, setTitle] = useState("");
  const [genreId, setGenreId] = useState<number | "">("");
  const [tagId, setTagId] = useState<number | "">("");
  const [demoId, setDemoId] = useState<number | "">("");
  const [page, setPage] = useState(1);

  function resetToFirstPage() {
    setPage(1);
  }

  const genresQ = useQuery({ queryKey: ["genres"], queryFn: getGenres, staleTime: 10 * 60_000 });
  const tagsQ = useQuery({ queryKey: ["tags"], queryFn: getTags, staleTime: 10 * 60_000 });
  const demosQ = useQuery({ queryKey: ["demographics"], queryFn: getDemographics, staleTime: 10 * 60_000 });

  const params = useMemo(
    () => ({
      title,
      page,
      size: 25,
      genre_id: genreId === "" ? null : genreId,
      tag_id: tagId === "" ? null : tagId,
      demo_id: demoId === "" ? null : demoId,
      order_by: "title" as const,
      order_dir: "asc" as const,
    }),
    [title, page, genreId, tagId, demoId]
  );

  const mangaQ = useQuery<MangaSearchResponse>({
    queryKey: ["mangas", params],
    queryFn: () => searchMangas(params),
    placeholderData: keepPreviousData,
  });

  const total = mangaQ.data?.total_results ?? 0;
  const size = mangaQ.data?.size ?? 25;
  const totalPages = Math.max(1, Math.ceil(total / size));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold">Search</h1>
        <p className="mt-1 text-sm opacity-80">Browse manga by title and filters.</p>
      </div>

      {/* Controls */}
      <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
        <div className="md:col-span-2">
          <label className="block text-sm mb-1">Title</label>
          <input
            className="w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2"
            placeholder="e.g. Naruto"
            value={title}
            onChange={(e) => {
              setTitle(e.target.value);
              resetToFirstPage();
            }}
          />
        </div>

        <div>
          <label className="block text-sm mb-1">Genre</label>
          <select
            className="w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2"
            value={genreId}
            onChange={(e) => {
              const v = e.target.value;
              setGenreId(v === "" ? "" : Number(v));
              resetToFirstPage();
            }}
          >
            <option value="">Any</option>
            {(genresQ.data ?? []).map((g) => (
              <option key={g.genre_id} value={g.genre_id}>
                {g.genre_name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm mb-1">Tag</label>
          <select
            className="w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2"
            value={tagId}
            onChange={(e) => {
              const v = e.target.value;
              setTagId(v === "" ? "" : Number(v));
              resetToFirstPage();
            }}
          >
            <option value="">Any</option>
            {(tagsQ.data ?? []).map((t) => (
              <option key={t.tag_id} value={t.tag_id}>
                {t.tag_name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm mb-1">Demographic</label>
          <select
            className="w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2"
            value={demoId}
            onChange={(e) => {
              const v = e.target.value;
              setDemoId(v === "" ? "" : Number(v));
              resetToFirstPage();
            }}
          >
            <option value="">Any</option>
            {(demosQ.data ?? []).map((d) => (
              <option key={d.demographic_id} value={d.demographic_id}>
                {d.demographic_name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Status */}
      {(genresQ.isLoading || tagsQ.isLoading || demosQ.isLoading) && (
        <div className="text-sm opacity-80">Loading filters…</div>
      )}

      {mangaQ.isLoading && <div className="text-sm opacity-80">Loading results…</div>}

      {mangaQ.isError && (
        <div className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">
          {(mangaQ.error as any)?.message ?? "Failed to load manga."}
        </div>
      )}

      {/* Results */}
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
          {(mangaQ.data?.items ?? []).map((m) => (
            <MangaCard
              key={m.manga_id}
              manga={
                {
                  manga_id: m.manga_id,
                  title: m.title,
                  cover_image_url: m.cover_image_url ?? null,
                } satisfies MangaCardManga
              }
            />
          ))}
        </div>

        {!mangaQ.isLoading && (mangaQ.data?.items?.length ?? 0) === 0 && (
          <div className="text-sm opacity-80">No results.</div>
        )}
      </div>

      {/* Paging */}
      <div className="flex items-center gap-3">
        <button
          className="rounded-md border border-neutral-700 px-3 py-2 disabled:opacity-50"
          disabled={page <= 1 || mangaQ.isLoading}
          onClick={() => setPage((p) => Math.max(1, p - 1))}
        >
          Prev
        </button>

        <button
          className="rounded-md border border-neutral-700 px-3 py-2 disabled:opacity-50"
          disabled={page >= totalPages || mangaQ.isLoading}
          onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
        >
          Next
        </button>
      </div>
    </div>
  );
}
