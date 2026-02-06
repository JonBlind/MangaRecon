import type {Genre, Tap, Demograpgic } from "./metadata";

export type MangaListItem = {
  manga_id: number;
  title: string;
  description?: string | null;
  cover_image_url?: string | null;
  average_rating?: number | null;
  external_average_rating?: number | null;
};

export type MangaSearchResponse = {
  total_results: number;
  page: number;
  size: number;
  items: MangaListItem[];
};

export type MangaSearchParams = {
  title?: string;
  page?: number;
  size?: number;

  genre_id?: number | null;
  tag_id?: number | null;
  demo_id?: number | null;

  order_by?: "title" | "average_rating" | "external_average_rating" | "published_date";
  order_dir?: "asc" | "desc";
};

export type MangaDetail = {
  manga_id: number;
  title: string;
  description?: string | null;
  published_date?: string | null;

  external_average_rating?: number | null;
  average_rating?: number | null;

  author_id: number;

  genres: Genre[];
  tags: Tag[];
  demographics: Demographic[];

  cover_image_url?: string | null;
};