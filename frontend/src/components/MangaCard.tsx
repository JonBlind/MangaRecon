import { Link } from "react-router-dom";
import type { MangaCardManga, MangaCardProps } from "../types/mangaCard";

export default function MangaCard({ manga }: MangaCardProps) {
  const genres = manga.genres?.slice(0, 3) ?? [];

  return (
    <Link
      to={`/manga/${manga.manga_id}`}
      className="group block overflow-hidden rounded-xl border border-neutral-800 bg-neutral-900 transition hover:border-neutral-600"
    >
      {/* Cover */}
      <div className="aspect-[2/3] overflow-hidden bg-neutral-800">
        <img
          src={manga.cover_image_url ?? "https://placehold.co/400x600?text=No+Cover"}
          alt={manga.title}
          className="h-full w-full object-cover transition-transform duration-200 group-hover:scale-105"
          onError={(e) => {
            e.currentTarget.src = "https://placehold.co/400x600?text=No+Cover";
          }}
        />
      </div>

      {/* Meta */}
      <div className="space-y-1 p-2">
        <div className="line-clamp-2 text-sm font-medium leading-tight">{manga.title}</div>

        {genres.length > 0 && (
          <div className="flex flex-wrap gap-x-2 gap-y-1 text-xs text-neutral-400">
            {genres.map((g) => (
              <span key={g.genre_id}>{g.genre_name}</span>
            ))}
          </div>
        )}
      </div>
    </Link>
  );
}