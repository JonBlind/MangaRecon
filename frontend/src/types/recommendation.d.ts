export type RecommendationOrderBy = "score" | "title" | "external_average_rating";

export type RecommendationOrderDir = "asc" | "desc";

export type RecommendationBreakdown = {
  genre_score: number;
  tag_score: number;
  demo_score: number;
  author_score: number;
  rating_score: number;
  year_score: number;
};

export type RecommendationItem = {
  manga_id: number;
  title: string;
  external_average_rating?: number | null;
  cover_image_url?: string | null;
  score: number;
  score_breakdown: RecommendationBreakdown;
};

export type RecommendationPage = {
  total_results: number;
  page: number;
  size: number;
  items: RecommendationItem[];

  seed_total?: number;
  seed_used?: number;
  seed_truncated?: boolean;
};

export type RecommendationParams = {
  page?: number;
  size?: number;
  order_by?: RecommendationOrderBy;
  order_dir?: RecommendationOrderDir;
};

export type RecommendationQueryListPayload = {
  manga_ids: number[];
};