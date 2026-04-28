import type { MangaListItem } from "./manga";

export type Collection = {
  collection_id: number;
  collection_name: string;
  description?: string | null;
  created_at: string;
};

export type CollectionCreatePayload = {
  collection_name: string;
  description?: string | null;
};

export type CollectionUpdatePayload = {
  collection_name?: string | null;
  description?: string | null;
};

export type Paginated<T> = {
  total_results: number;
  page: number;
  size: number;
  items: T[];
};

export type ListCollectionsParams = {
  page?: number;
  size?: number;
  order?: "asc" | "desc";
};

export type ListCollectionMangaParams = {
  page?: number;
  size?: number;
  order?: "asc" | "desc";
};

export type BulkAddFailureReason =
  | "ALREADY_EXISTS"
  | "COLLECTION_NOT_FOUND"
  | "UNKNOWN";

export type BulkAddFailure = {
  manga_id: number;
  reason: BulkAddFailureReason;
};

export type BulkAddMangaResponse = {
  collection_id: number;
  added_count: number;
  failed_count: number;
  added_ids: number[];
  failed: BulkAddFailure[];
};

export type CollectionMangaPage = Paginated<MangaListItem>;
export type CollectionPage = Paginated<Collection>;
