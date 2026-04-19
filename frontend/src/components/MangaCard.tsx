import { Link, useLocation } from "react-router-dom";
import type { MangaListItem } from "../types/manga";

type MangaCardProps = {
  manga: MangaListItem;
  selectable?: boolean;
  selected?: boolean;
  onToggleSelect?: (manga: MangaListItem) => void;
};

const FALLBACK_COVER = "https://placehold.co/400x600?text=No+Cover";

export default function MangaCard({
  manga,
  selectable = false,
  selected = false,
  onToggleSelect,
}: MangaCardProps) {
  const location = useLocation();
  const returnTo = `${location.pathname}${location.search}${location.hash}`;

  return (
    <Link
      to={`/manga/${manga.manga_id}`}
      state={{ returnTo }}
      title={manga.title}
      className={[
        "group relative block overflow-hidden rounded-xl border bg-neutral-900 transition",
        selected
          ? "border-neutral-300 ring-2 ring-neutral-300/70"
          : "border-neutral-800 hover:border-neutral-600",
      ].join(" ")}
    >
      {selectable && onToggleSelect && (
        <button
          type="button"
          aria-label={selected ? `Deselect ${manga.title}` : `Select ${manga.title}`}
          title={selected ? "Deselect" : "Select"}
          className={[
            "absolute right-2 top-2 z-10 flex h-8 w-8 items-center justify-center rounded-full border text-sm font-semibold transition",
            selected
              ? "border-neutral-200 bg-neutral-100 text-neutral-950"
              : "border-neutral-700 bg-neutral-900/90 text-neutral-100 opacity-0 group-hover:opacity-100",
          ].join(" ")}
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onToggleSelect(manga);
          }}
        >
          {selected ? "✓" : "+"}
        </button>
      )}

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