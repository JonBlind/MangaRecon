import { ApiRequestError, apiFetch } from "./http";
import type { Rating, RatingPayload } from "../types/rating";

export async function getRatingForManga(mangaId: number): Promise<Rating | null> {
  try {
    const res = await apiFetch<Rating>(`/ratings?manga_id=${mangaId}`, {
      method: "GET",
    });
    return res.data;
  } catch (error) {
    if (error instanceof ApiRequestError && error.statusCode === 404) {
      return null;
    }
    throw error;
  }
}

export async function saveRating(payload: RatingPayload): Promise<Rating> {
  const res = await apiFetch<Rating>("/ratings", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return res.data;
}

export async function deleteRating(mangaId: number): Promise<void> {
  await apiFetch(`/ratings/${mangaId}`, {
    method: "DELETE",
  });
}
