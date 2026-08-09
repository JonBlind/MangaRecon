export type Rating = {
  manga_id: number;
  personal_rating: number;
  created_at: string;
};

export type RatingPayload = {
  manga_id: number;
  personal_rating: number;
};
