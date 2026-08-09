import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { deleteRating, getRatingForManga, saveRating } from "../api/ratings";
import { recommendationKeys } from "./useRecommendations";

export const ratingKeys = {
  all: ["ratings"] as const,
  detail: (mangaId: number) => ["ratings", mangaId] as const,
};

function invalidateMangaRatingDependents(
  queryClient: ReturnType<typeof useQueryClient>,
  mangaId: number,
) {
  queryClient.invalidateQueries({ queryKey: ["manga", mangaId] });
  queryClient.invalidateQueries({ queryKey: ["mangas"] });
  queryClient.invalidateQueries({ queryKey: recommendationKeys.collections });
}

export function useRating(mangaId: number, enabled: boolean) {
  return useQuery({
    queryKey: ratingKeys.detail(mangaId),
    queryFn: () => getRatingForManga(mangaId),
    enabled: enabled && Number.isInteger(mangaId) && mangaId > 0,
    retry: false,
    staleTime: 60_000,
  });
}

export function useSaveRating(mangaId: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (personalRating: number) =>
      saveRating({
        manga_id: mangaId,
        personal_rating: personalRating,
      }),
    onSuccess: (rating) => {
      queryClient.setQueryData(ratingKeys.detail(mangaId), rating);
      invalidateMangaRatingDependents(queryClient, mangaId);
    },
  });
}

export function useDeleteRating(mangaId: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => deleteRating(mangaId),
    onSuccess: () => {
      queryClient.setQueryData(ratingKeys.detail(mangaId), null);
      invalidateMangaRatingDependents(queryClient, mangaId);
    },
  });
}
