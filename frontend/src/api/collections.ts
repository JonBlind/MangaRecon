import { apiFetch } from "./http";
import type {
  Collection,
  CollectionCreatePayload,
  CollectionUpdatePayload,
  CollectionPage,
  CollectionMangaPage,
  ListCollectionsParams,
  ListCollectionMangaParams,
} from "../types/collection";

function buildPaginationParams(
  params: { page?: number; size?: number; order?: string },
  defaults = { page: 1, size: 20, order: "desc" }
) {
  const sp = new URLSearchParams();
  sp.set("page", String(params.page ?? defaults.page));
  sp.set("size", String(params.size ?? defaults.size));
  sp.set("order", params.order ?? defaults.order);
  return sp.toString();
}

export async function listCollections(
  params: ListCollectionsParams = {}
): Promise<CollectionPage> {
  const qs = buildPaginationParams(params);
  const res = await apiFetch<CollectionPage>(`/collections?${qs}`, {
    method: "GET",
  });
  return res.data;
}

export async function getCollectionById(
  collectionId: number
): Promise<Collection> {
  const res = await apiFetch<Collection>(`/collections/${collectionId}`, {
    method: "GET",
  });
  return res.data;
}

export async function createCollection(
  payload: CollectionCreatePayload
): Promise<Collection> {
  const res = await apiFetch<Collection>("/collections", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return res.data;
}

export async function updateCollection(
  collectionId: number,
  payload: CollectionUpdatePayload
): Promise<Collection> {
  const res = await apiFetch<Collection>(`/collections/${collectionId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  return res.data;
}

export async function deleteCollection(collectionId: number): Promise<void> {
  await apiFetch<void>(`/collections/${collectionId}`, {
    method: "DELETE",
  });
}

export async function listMangaInCollection(
  collectionId: number,
  params: ListCollectionMangaParams = {}
): Promise<CollectionMangaPage> {
  const qs = buildPaginationParams(params);
  const res = await apiFetch<CollectionMangaPage>(
    `/collections/${collectionId}/mangas?${qs}`,
    { method: "GET" }
  );
  return res.data;
}

export async function addMangaToCollection(
  collectionId: number,
  mangaId: number
): Promise<void> {
  await apiFetch<void>(`/collections/${collectionId}/mangas`, {
    method: "POST",
    body: JSON.stringify({ manga_id: mangaId }),
  });
}

export async function removeMangaFromCollection(
  collectionId: number,
  mangaId: number
): Promise<void> {
  await apiFetch<void>(`/collections/${collectionId}/mangas`, {
    method: "DELETE",
    body: JSON.stringify({ manga_id: mangaId }),
  });
}
