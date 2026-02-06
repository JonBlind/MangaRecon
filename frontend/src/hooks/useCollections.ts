import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  addMangaToCollection,
  createCollection,
  deleteCollection,
  getCollectionById,
  listCollections,
  listMangaInCollection,
  removeMangaFromCollection,
  updateCollection,
} from "../api/collections";
import type {
  Collection,
  CollectionCreatePayload,
  CollectionUpdatePayload,
  CollectionPage,
  CollectionMangaPage,
  ListCollectionsParams,
  ListCollectionMangaParams,
} from "../types/collection";

export const collectionsKeys = {
  all: ["collections"] as const,
  list: (params: ListCollectionsParams) =>
    ["collections", "list", params] as const,
  detail: (collectionId: number) =>
    ["collections", "detail", collectionId] as const,
  mangas: (collectionId: number, params: ListCollectionMangaParams) =>
    ["collections", "mangas", collectionId, params] as const,
};

export function useCollections(params: ListCollectionsParams = {}) {
  const normalized = {
    page: params.page ?? 1,
    size: params.size ?? 20,
    order: params.order ?? "desc",
  };

  return useQuery<CollectionPage>({
    queryKey: collectionsKeys.list(normalized),
    queryFn: () => listCollections(normalized),
    retry: false,
    staleTime: 60_000,
  });
}

export function useCollection(collectionId: number) {
  return useQuery<Collection>({
    queryKey: collectionsKeys.detail(collectionId),
    queryFn: () => getCollectionById(collectionId),
    enabled: Number.isFinite(collectionId) && collectionId > 0,
    retry: false,
    staleTime: 60_000,
  });
}

export function useCollectionManga(
  collectionId: number,
  params: ListCollectionMangaParams = {}
) {
  const normalized = {
    page: params.page ?? 1,
    size: params.size ?? 20,
    order: params.order ?? "desc",
  };

  return useQuery<CollectionMangaPage>({
    queryKey: collectionsKeys.mangas(collectionId, normalized),
    queryFn: () => listMangaInCollection(collectionId, normalized),
    enabled: Number.isFinite(collectionId) && collectionId > 0,
    retry: false,
    staleTime: 30_000,
  });
}

export function useCreateCollection() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: (payload: CollectionCreatePayload) =>
      createCollection(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: collectionsKeys.all });
    },
  });
}

export function useUpdateCollection(collectionId: number) {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: (payload: CollectionUpdatePayload) =>
      updateCollection(collectionId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: collectionsKeys.all });
      qc.invalidateQueries({ queryKey: collectionsKeys.detail(collectionId) });
      qc.invalidateQueries({
        queryKey: ["collections", "mangas", collectionId],
      });
    },
  });
}

export function useDeleteCollection() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: (collectionId: number) => deleteCollection(collectionId),
    onSuccess: (_data, collectionId) => {
      qc.invalidateQueries({ queryKey: collectionsKeys.all });
      qc.removeQueries({
        queryKey: collectionsKeys.detail(collectionId),
      });
      qc.removeQueries({
        queryKey: ["collections", "mangas", collectionId],
      });
    },
  });
}

export function useAddMangaToCollection(collectionId: number) {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: (mangaId: number) =>
      addMangaToCollection(collectionId, mangaId),
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: ["collections", "mangas", collectionId],
      });
      qc.invalidateQueries({ queryKey: collectionsKeys.all });
    },
  });
}

export function useRemoveMangaFromCollection(collectionId: number) {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: (mangaId: number) =>
      removeMangaFromCollection(collectionId, mangaId),
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: ["collections", "mangas", collectionId],
      });
      qc.invalidateQueries({ queryKey: collectionsKeys.all });
    },
  });
}
