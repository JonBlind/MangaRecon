import { useMemo, useState } from "react";
import type { MangaListItem } from "../types/manga";

type SelectedMangaMap = Record<number, MangaListItem>;

export function useMangaSelection() {
  const [selectedById, setSelectedById] = useState<SelectedMangaMap>({});

  function toggleSelection(manga: MangaListItem) {
    setSelectedById((prev) => {
      const next = { ...prev };

      if (next[manga.manga_id]) {
        delete next[manga.manga_id];
      } else {
        next[manga.manga_id] = manga;
      }

      return next;
    });
  }

  function clearSelection() {
    setSelectedById({});
  }

  function isSelected(mangaId: number): boolean {
    return Boolean(selectedById[mangaId]);
  }

  const selectedItems = useMemo(
    () => Object.values(selectedById),
    [selectedById]
  );

  const selectedIds = useMemo(
    () => selectedItems.map((manga) => manga.manga_id),
    [selectedItems]
  );

  const selectedCount = selectedItems.length;

  return {
    selectedItems,
    selectedIds,
    selectedCount,
    toggleSelection,
    clearSelection,
    isSelected,
  };
}