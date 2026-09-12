import { apiFetch } from "./http";
import type { MangaSearchParams, MangaSearchResponse } from "../types/manga";
import type { MangaDetail } from "../types/manga";

export async function getMangaById(mangaId: number): Promise<MangaDetail> {
  const res = await apiFetch<MangaDetail>(`/mangas/${mangaId}`);
  return res.data;
}

export async function searchMangas(
  params: MangaSearchParams,
  signal?: AbortSignal,
): Promise<MangaSearchResponse> {
  const sp = new URLSearchParams();

  if (params.title?.trim()) sp.set("title", params.title.trim());
  sp.set("page", String(params.page ?? 1));
  sp.set("size", String(params.size ?? 50));

  if (params.order_by) sp.set("order_by", params.order_by);
  if (params.order_dir) sp.set("order_dir", params.order_dir);

  for (const genreId of params.genre_ids ?? []) {
    sp.append("genre_ids", String(genreId));
  }
  for (const genreId of params.exclude_genres ?? []) {
    sp.append("exclude_genres", String(genreId));
  }
  for (const tagId of params.tag_ids ?? []) {
    sp.append("tag_ids", String(tagId));
  }
  for (const tagId of params.exclude_tags ?? []) {
    sp.append("exclude_tags", String(tagId));
  }
  for (const demoId of params.demo_ids ?? []) {
    sp.append("demo_ids", String(demoId));
  }
  for (const demoId of params.exclude_demos ?? []) {
    sp.append("exclude_demos", String(demoId));
  }
  if (params.match_mode) sp.set("match_mode", params.match_mode);

  const path = `/mangas/?${sp}`;
  const res = signal
    ? await apiFetch<MangaSearchResponse>(path, { signal })
    : await apiFetch<MangaSearchResponse>(path);

  return res.data;
}
