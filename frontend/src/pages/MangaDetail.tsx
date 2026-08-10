import { Link, useLocation, useParams } from "react-router-dom";
import { useEffect, useState } from "react";
import { useManga } from "../hooks/useManga";
import { useMe } from "../hooks/useMe";
import { useCollections, useAddMangaToCollection } from "../hooks/useCollections";
import { useDeleteRating, useRating, useSaveRating } from "../hooks/useRatings";
import type { FeedbackMessage, ReturnToLocationState } from "../types/ui";

const FALLBACK_COVER = "https://placehold.co/400x600?text=No+Cover";

const RATING_STARS = [1, 2, 3, 4, 5] as const;
const COLLAPSED_TAG_LIMIT = 12;

function formatStarRating(personalRating: number) {
  return (personalRating / 2).toFixed(1);
}

export default function MangaDetail() {
  const { id } = useParams();
  const location = useLocation();
  const state = location.state as ReturnToLocationState | null;
  const backTo = state?.returnTo || "/search";

  const mangaId = Number(id);

  if (!Number.isFinite(mangaId) || mangaId <= 0) {
    return <div className="p-6">Invalid manga id.</div>;
  }

  const { data, isPending, isError } = useManga(mangaId);

  // auth + collections
  const meQ = useMe();
  const collectionsQ = useCollections({
    page: 1,
    size: 100,
  });
  const [selectedCollection, setSelectedCollection] = useState<number | "">("");
  const [feedback, setFeedback] = useState<FeedbackMessage | null>(null);
  const addM = useAddMangaToCollection(
    typeof selectedCollection === "number" ? selectedCollection : -1,
  );
  const isAuthenticated = Boolean(meQ.data);
  const ratingQ = useRating(mangaId, isAuthenticated);
  const saveRatingM = useSaveRating(mangaId);
  const deleteRatingM = useDeleteRating(mangaId);
  const [selectedRating, setSelectedRating] = useState<number | "">("");
  const [previewRating, setPreviewRating] = useState<number | null>(null);
  const [ratingFeedback, setRatingFeedback] = useState<FeedbackMessage | null>(null);
  const [showAllTags, setShowAllTags] = useState(false);

  useEffect(() => {
    setFeedback(null);
    setPreviewRating(null);
    setRatingFeedback(null);
    setShowAllTags(false);
  }, [mangaId]);

  useEffect(() => {
    if (!isAuthenticated || !ratingQ.isSuccess) {
      return;
    }

    setSelectedRating(ratingQ.data?.personal_rating ?? "");
  }, [isAuthenticated, mangaId, ratingQ.data, ratingQ.isSuccess]);

  if (isPending) {
    return <div className="p-6">Loading manga…</div>;
  }

  if (isError || !data) {
    return <div className="p-6">Couldn't load this manga.</div>;
  }

  const m = data;
  const demographics = m.demographics ?? [];
  const genres = m.genres ?? [];
  const tags = m.tags ?? [];
  const creatorCredits = m.creator_credits ?? [];

  const authors = creatorCredits.filter((credit) => credit.role === "author");
  const artists = creatorCredits.filter((credit) => credit.role === "artist");
  const displayedRating =
    previewRating ?? (typeof selectedRating === "number" ? selectedRating : 0);
  const visibleTags = showAllTags
    ? tags
    : tags.slice(0, COLLAPSED_TAG_LIMIT);

  const tagsAreCollapsible = tags.length > COLLAPSED_TAG_LIMIT;

  async function handleAdd() {
    if (typeof selectedCollection !== "number") {
      return;
    }

    setFeedback(null);

    try {
      await addM.mutateAsync(mangaId);
      setSelectedCollection("");
      setFeedback({
        type: "success",
        message: "Manga added to collection.",
      });
    } catch (e: any) {
      setFeedback({
        type: "error",
        message: e?.message ?? "Failed to add manga to collection.",
      });
    }
  }

  async function handleSelectRating(personalRating: number) {
    const previousRating = selectedRating;
    setRatingFeedback(null);
    setPreviewRating(null);
    setSelectedRating(personalRating);

    try {
      await saveRatingM.mutateAsync(personalRating);
      setRatingFeedback({
        type: "success",
        message: "Your rating was saved.",
      });
    } catch (error) {
      setSelectedRating(previousRating);
      setRatingFeedback({
        type: "error",
        message: error instanceof Error ? error.message : "Failed to save your rating.",
      });
    }
  }

  async function handleDeleteRating() {
    setRatingFeedback(null);

    try {
      await deleteRatingM.mutateAsync();
      setSelectedRating("");
      setPreviewRating(null);
      setRatingFeedback({
        type: "success",
        message: "Your rating was removed.",
      });
    } catch (error) {
      setRatingFeedback({
        type: "error",
        message: error instanceof Error ? error.message : "Failed to remove your rating.",
      });
    }
  }

  return (
    <div className="space-y-6 p-6">
      <div>
        <Link to={backTo} className="text-sm text-neutral-400 hover:text-neutral-200">
          ← Back to results
        </Link>
      </div>

      <div className="flex flex-col gap-6 md:flex-row">
        <img
          src={m.cover_image_url ?? FALLBACK_COVER}
          alt={m.title}
          className="h-72 w-48 rounded-xl border border-neutral-800 bg-neutral-900 object-cover"
          onError={(e) => {
            e.currentTarget.src = FALLBACK_COVER;
          }}
        />

        <div className="min-w-0 flex-1 space-y-4">
          <h1 className="text-3xl font-bold">{m.title}</h1>

          {(authors.length > 0 || artists.length > 0) && (
            <div className="space-y-1 text-sm opacity-80">
              {authors.length > 0 && (
                <p>
                  <span className="font-medium">
                    {authors.length === 1 ? "Author:" : "Authors:"}
                  </span>{" "}
                  {authors.map((credit) => credit.creator_name).join(", ")}
                </p>
              )}

              {artists.length > 0 && (
                <p>
                  <span className="font-medium">
                    {artists.length === 1 ? "Artist:" : "Artists:"}
                  </span>{" "}
                  {artists.map((credit) => credit.creator_name).join(", ")}
                </p>
              )}
            </div>
          )}

          {!meQ.isPending && meQ.data && (
            <div className="space-y-3">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                <select
                  className="rounded-md border border-neutral-700 bg-neutral-950 px-3 py-2 text-sm"
                  value={selectedCollection}
                  onChange={(e) => {
                    setFeedback(null);
                    setSelectedCollection(e.target.value ? Number(e.target.value) : "");
                  }}
                  disabled={collectionsQ.isLoading || addM.isPending}
                >
                  <option value="">Add to collection…</option>

                  {(collectionsQ.data?.items ?? []).map((c) => (
                    <option key={c.collection_id} value={c.collection_id}>
                      {c.collection_name}
                    </option>
                  ))}
                </select>

                <button
                  className="rounded-md border border-neutral-700 px-3 py-2 text-sm hover:bg-neutral-900 disabled:opacity-50"
                  disabled={
                    typeof selectedCollection !== "number" ||
                    addM.isPending ||
                    collectionsQ.isLoading
                  }
                  onClick={handleAdd}
                >
                  {addM.isPending ? "Adding…" : "Add"}
                </button>
              </div>

              {collectionsQ.isLoading && (
                <p className="text-sm opacity-70">Loading collections…</p>
              )}

              {!collectionsQ.isLoading &&
                (collectionsQ.data?.items?.length ?? 0) === 0 && (
                  <p className="text-sm opacity-70">
                    You don't have any collections yet.
                  </p>
                )}

              {feedback && (
                <p
                  className={
                    feedback.type === "success"
                      ? "text-sm text-green-400"
                      : "text-sm text-red-400"
                  }
                >
                  {feedback.message}
                </p>
              )}

              <div className="space-y-2 rounded-lg border border-neutral-800 p-3">
                <p className="text-sm font-medium">Your rating</p>

                {ratingQ.isPending ? (
                  <p className="text-sm opacity-70">Loading your rating…</p>
                ) : ratingQ.isError ? (
                  <p className="text-sm text-red-400">Failed to load your rating.</p>
                ) : (
                  <>
                    <fieldset
                      className="space-y-2"
                      disabled={saveRatingM.isPending || deleteRatingM.isPending}
                    >
                      <legend className="sr-only">Your rating</legend>

                      <div
                        className="inline-flex"
                        onMouseLeave={() => setPreviewRating(null)}
                      >
                        {RATING_STARS.map((star) => {
                          const previousFullRating = (star - 1) * 2;
                          const halfRating = star * 2 - 1;
                          const fullRating = star * 2;

                          const fillPercentage = Math.max(
                            0,
                            Math.min(100, (displayedRating - previousFullRating) * 50),
                          );

                          const previousInputId =
                            previousFullRating > 0
                              ? `personal-rating-${mangaId}-${previousFullRating}`
                              : undefined;

                          return (
                            <div key={star} className="relative h-9 w-9">
                              <svg
                                aria-hidden="true"
                                viewBox="0 0 24 24"
                                className="pointer-events-none absolute inset-0 h-9 w-9 text-neutral-600"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="1.5"
                                strokeLinejoin="round"
                              >
                                <path d="M12 2.25 14.918 8.163 21.445 9.112 16.723 13.715 17.838 20.216 12 17.146 6.162 20.216 7.277 13.715 2.555 9.112 9.082 8.163 12 2.25Z" />
                              </svg>

                              <span
                                aria-hidden="true"
                                className="pointer-events-none absolute inset-y-0 left-0 overflow-hidden transition-[width]"
                                style={{ width: `${fillPercentage}%` }}
                              >
                                <svg
                                  viewBox="0 0 24 24"
                                  className="h-9 w-9 max-w-none fill-yellow-400 text-yellow-400"
                                  stroke="currentColor"
                                  strokeWidth="1.5"
                                  strokeLinejoin="round"
                                >
                                  <path d="M12 2.25 14.918 8.163 21.445 9.112 16.723 13.715 17.838 20.216 12 17.146 6.162 20.216 7.277 13.715 2.555 9.112 9.082 8.163 12 2.25Z" />
                                </svg>
                              </span>

                              {previousInputId ? (
                                <label
                                  htmlFor={previousInputId}
                                  className="absolute inset-y-0 left-0 z-10 w-1/4 cursor-pointer"
                                  title={`Rate ${formatStarRating(previousFullRating)} out of 5 stars`}
                                  onMouseEnter={() => setPreviewRating(previousFullRating)}
                                >
                                  <span className="sr-only">
                                    {formatStarRating(previousFullRating)} out of 5 stars
                                  </span>
                                </label>
                              ) : (
                                <span
                                  aria-hidden="true"
                                  className="absolute inset-y-0 left-0 z-10 w-1/4"
                                  onMouseEnter={() => setPreviewRating(0)}
                                />
                              )}

                              {[
                                {
                                  value: halfRating,
                                  positionClass: "left-1/4 w-1/2",
                                },
                                {
                                  value: fullRating,
                                  positionClass: "right-0 w-1/4",
                                },
                              ].map(({ value, positionClass }) => {
                                const starValue = formatStarRating(value);
                                const inputId = `personal-rating-${mangaId}-${value}`;

                                return (
                                  <span
                                    key={value}
                                    className={`absolute inset-y-0 z-10 ${positionClass}`}
                                  >
                                    <input
                                      id={inputId}
                                      className="peer sr-only"
                                      type="radio"
                                      name={`personal-rating-${mangaId}`}
                                      value={value}
                                      checked={selectedRating === value}
                                      onChange={() => void handleSelectRating(value)}
                                      onFocus={() => setPreviewRating(value)}
                                      onBlur={() => setPreviewRating(null)}
                                    />

                                    <label
                                      htmlFor={inputId}
                                      className="absolute inset-0 cursor-pointer rounded-sm peer-focus-visible:ring-2 peer-focus-visible:ring-yellow-300 peer-disabled:cursor-not-allowed"
                                      title={`Rate ${starValue} out of 5 stars`}
                                      onMouseEnter={() => setPreviewRating(value)}
                                    >
                                      <span className="sr-only">
                                        {starValue} out of 5 stars
                                      </span>
                                    </label>
                                  </span>
                                );
                              })}
                            </div>
                          );
                        })}
                      </div>
                    </fieldset>

                    <div className="flex flex-wrap items-center gap-3">
                      {typeof selectedRating === "number" && (
                        <button
                          type="button"
                          className="text-sm text-red-300 hover:text-red-200 disabled:opacity-50"
                          disabled={saveRatingM.isPending || deleteRatingM.isPending}
                          onClick={handleDeleteRating}
                        >
                          {deleteRatingM.isPending ? "Removing…" : "Remove rating"}
                        </button>
                      )}
                    </div>
                  </>
                )}

                {ratingFeedback && (
                  <p
                    className={
                      ratingFeedback.type === "success"
                        ? "text-sm text-green-400"
                        : "text-sm text-red-400"
                    }
                  >
                    {ratingFeedback.message}
                  </p>
                )}
              </div>
            </div>
          )}

          <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm opacity-80">
            {m.published_date ? <span>Published: {m.published_date}</span> : null}

            {m.average_rating != null ? (
              <span>User avg: {(m.average_rating / 2).toFixed(1)} / 5</span>
            ) : null}

            {m.external_average_rating != null ? (
              <span>External Rating: {m.external_average_rating} / 10</span>
            ) : null}
          </div>

          {(demographics.length > 0 || genres.length > 0 || tags.length > 0) && (
            <div className="space-y-4">
              {demographics.length > 0 && (
                <section
                  aria-labelledby={`demographics-heading-${mangaId}`}
                  className="space-y-2"
                >
                  <h2
                    id={`demographics-heading-${mangaId}`}
                    className="text-sm font-semibold text-neutral-300"
                  >
                    Demographics
                  </h2>

                  <div className="flex flex-wrap gap-2">
                    {demographics.map((demographic) => (
                      <span
                        key={demographic.demographic_id}
                        className="rounded bg-violet-950/60 px-2 py-1 text-sm text-violet-200"
                      >
                        {demographic.demographic_name}
                      </span>
                    ))}
                  </div>
                </section>
              )}

              {genres.length > 0 && (
                <section
                  aria-labelledby={`genres-heading-${mangaId}`}
                  className="space-y-2"
                >
                  <h2
                    id={`genres-heading-${mangaId}`}
                    className="text-sm font-semibold text-neutral-300"
                  >
                    Genres
                  </h2>

                  <div className="flex flex-wrap gap-2">
                    {genres.map((genre) => (
                      <span
                        key={genre.genre_id}
                        className="rounded bg-sky-950/60 px-2 py-1 text-sm text-sky-200"
                      >
                        {genre.genre_name}
                      </span>
                    ))}
                  </div>
                </section>
              )}

              {tags.length > 0 && (
                <section
                  aria-labelledby={`tags-heading-${mangaId}`}
                  className="space-y-2"
                >
                  <h2
                    id={`tags-heading-${mangaId}`}
                    className="text-sm font-semibold text-neutral-300"
                  >
                    Tags
                  </h2>

                  <div
                    id={`manga-tags-${mangaId}`}
                    className="flex flex-wrap gap-2"
                  >
                    {visibleTags.map((tag) => (
                      <span
                        key={tag.tag_id}
                        className="rounded bg-neutral-800 px-2 py-1 text-sm text-neutral-200"
                      >
                        {tag.tag_name}
                      </span>
                    ))}
                  </div>

                  {tagsAreCollapsible && (
                    <button
                      type="button"
                      className="text-sm text-sky-400 hover:text-sky-300"
                      aria-expanded={showAllTags}
                      aria-controls={`manga-tags-${mangaId}`}
                      onClick={() => setShowAllTags((currentlyShown) => !currentlyShown)}
                    >
                      {showAllTags
                        ? "Show fewer tags"
                        : `Show all ${tags.length} tags`}
                    </button>
                  )}
                </section>
              )}
            </div>
          )}

          <section
            aria-labelledby={`description-heading-${mangaId}`}
            className="space-y-2 border-t border-neutral-800 pt-4"
          >
            <h2
              id={`description-heading-${mangaId}`}
              className="text-sm font-semibold text-neutral-300"
            >
              Description
            </h2>

            {m.description ? (
              <p className="whitespace-pre-line leading-relaxed">
                {m.description}
              </p>
            ) : (
              <p className="opacity-70">No description available.</p>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
