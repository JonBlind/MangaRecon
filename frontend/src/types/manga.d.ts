import type { Genre, Tag, Demographic } from "./metadata";

export type MangaListItem = {
  manga_id: number;
  title: string;
  description?: string | null;
  cover_image_url?: string | null;
  average_rating?: number | null;
  external_average_rating?: number | null;
  genres?: Genre[];
};

export type MangaSearchResponse = {
  total_results: number;
  page: number;
  size: number;
  items: MangaListItem[];
};

export type MetadataMatchMode = "and" | "or";

export type MangaSearchParams = {
  title?: string;
  page?: number;
  size?: number;

  genre_ids?: number[];
  exclude_genres?: number[];
  tag_ids?: number[];
  exclude_tags?: number[];
  demo_ids?: number[];
  exclude_demos?: number[];
  match_mode?: MetadataMatchMode;

  order_by?: "title" | "average_rating" | "external_average_rating" | "published_year";
  order_dir?: "asc" | "desc";
};

export type CreatorCredit = {
  creator_id: number;
  creator_name: string;
  role: "author" | "artist";
};

export type MangaDetail = {
  manga_id: number;
  title: string;
  description?: string | null;
  publication_year?: number | null;
  media_type?: string | null;

  external_average_rating?: number | null;
  average_rating?: number | null;

  creator_credits: CreatorCredit[];

  genres: Genre[];
  tags: Tag[];
  demographics: Demographic[];

  cover_image_url?: string | null;
};
