import { apiFetch } from "./http";
import type { MangaSearchParams, MangaSearchResponse } from "../types/manga";
import type { MangaDetail } from "../types/manga";

export async function getMangaById(mangaId: number): Promise<MangaDetail> {
  const res = await apiFetch<MangaDetail>(`/mangas/${mangaId}`);
  return res.data;
}

export async function searchMangas(params: MangaSearchParams): Promise<MangaSearchResponse> {
  const sp = new URLSearchParams();

  if (params.title?.trim()) sp.set("title", params.title.trim());
  sp.set("page", String(params.page ?? 1));
  sp.set("size", String(params.size ?? 50));

  if (params.order_by) sp.set("order_by", params.order_by);
  if (params.order_dir) sp.set("order_dir", params.order_dir);

  if (params.genre_id) sp.append("genre_ids", String(params.genre_id));
  if (params.tag_id) sp.append("tag_ids", String(params.tag_id));
  if (params.demo_id) sp.append("demo_ids", String(params.demo_id));

  const res = await apiFetch<MangaSearchResponse>(`/mangas/?${sp}`);
  return res.data;
}