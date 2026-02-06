import { useQuery } from "@tanstack/react-query";
import { getMangaById } from "../api/manga";
import type { MangaDetail } from "../types/manga";

export function useManga(mangaId: number) {
  return useQuery<MangaDetail>({
    queryKey: ["manga", mangaId],
    queryFn: () => getMangaById(mangaId),
    retry: false,
    staleTime: 60_000,
    enabled: Number.isFinite(mangaId) && mangaId > 0,
  });
}
