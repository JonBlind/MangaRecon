import { Link, useLocation } from "react-router-dom";
import type { MangaListItem } from "../types/manga";

type MangaCardProps = {
  manga: MangaListItem;
};

const FALLBACK_COVER = "https://placehold.co/400x600?text=No+Cover";

export default function MangaCard({ manga }: MangaCardProps) {
  const location = useLocation();
  const returnTo = `${location.pathname}${location.search}${location.hash}`;

  return (
    <Link
      to={`/manga/${manga.manga_id}`}
      state={{ returnTo }}
      title={manga.title}
      className="group block overflow-hidden rounded-xl border border-neutral-800 bg-neutral-900 transition hover:border-neutral-600"
    >
      <div className="aspect-[2/3] w-full overflow-hidden bg-neutral-950">
        <img
          src={manga.cover_image_url || FALLBACK_COVER}
          alt={manga.title}
          className="h-full w-full object-cover transition group-hover:scale-[1.02]"
        />
      </div>

      <div className="flex min-h-[72px] items-start p-3">
        <h2 className="line-clamp-2 text-sm font-semibold leading-5">
          {manga.title}
        </h2>
      </div>
    </Link>
  );
}