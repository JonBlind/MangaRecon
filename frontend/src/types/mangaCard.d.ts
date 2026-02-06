export type MangaCardGenre = {
  genre_id: number;
  genre_name: string;
};

export type MangaCardManga = {
  manga_id: number;
  title: string;
  cover_image_url?: string | null;
  genres?: MangaCardGenre[];
};

type MangaCardProps = {
  manga: MangaCardManga;
};
