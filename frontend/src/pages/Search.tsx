import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  keepPreviousData,
  useIsFetching,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { getDemographics, getGenres, getTags } from "../api/metadata";
import { searchMangas } from "../api/manga";
import { addMangasBulkToCollection } from "../api/collections";
import type { MangaSearchResponse, MetadataMatchMode } from "../types/manga";
import MangaCard from "../components/MangaCard";
import MetadataMultiSelect, {
  type MetadataSelection,
} from "../components/MetadataMultiSelect";
import SearchSelectionBar from "../components/SearchSelectionBar";
import CollectionPickerModal from "../components/CollectionPickerModal";
import AuthRequiredModal from "../components/AuthRequiredModal";
import { useMangaSelection } from "../hooks/useMangaSelection";
import { useMe } from "../hooks/useMe";
import { recommendationKeys } from "../hooks/useRecommendations";

const SEARCH_DEBOUNCE_MS = 250;

type SearchParamValue = string | number | readonly (string | number)[] | null | undefined;

function parseSelectedIds(searchParams: URLSearchParams, key: string): number[] {
  return Array.from(
    new Set(
      searchParams
        .getAll(key)
        .map(Number)
        .filter((id) => Number.isInteger(id) && id > 0),
    ),
  );
}

function parseMetadataSelection(
  searchParams: URLSearchParams,
  includedKey: string,
  excludedKey: string,
): MetadataSelection {
  const excludedIds = parseSelectedIds(searchParams, excludedKey);
  const excludedSet = new Set(excludedIds);

  return {
    includedIds: parseSelectedIds(searchParams, includedKey).filter(
      (id) => !excludedSet.has(id),
    ),
    excludedIds,
  };
}

export default function Search() {
  const nav = useNavigate();
  const qc = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [isCollectionModalOpen, setIsCollectionModalOpen] = useState(false);
  const [isAuthRequiredModalOpen, setIsAuthRequiredModalOpen] = useState(false);
  const [isBulkAdding, setIsBulkAdding] = useState(false);
  const [bulkAddFeedback, setBulkAddFeedback] = useState<string | null>(null);

  const title = searchParams.get("title") ?? "";
  const [titleInput, setTitleInput] = useState(title);
  const genreSelection = useMemo(
    () => parseMetadataSelection(searchParams, "genre", "exclude_genre"),
    [searchParams],
  );
  const tagSelection = useMemo(
    () => parseMetadataSelection(searchParams, "tag", "exclude_tag"),
    [searchParams],
  );
  const demoSelection = useMemo(
    () => parseMetadataSelection(searchParams, "demo", "exclude_demo"),
    [searchParams],
  );
  const matchMode: MetadataMatchMode = searchParams.get("match") === "or" ? "or" : "and";
  const page = Number(searchParams.get("page") ?? "1");
  const [tagFilterActivated, setTagFilterActivated] = useState(
    tagSelection.includedIds.length + tagSelection.excludedIds.length > 0,
  );

  const {
    selectedIds,
    selectedCount,
    toggleSelection,
    clearSelection,
    removeSelectedIds,
    isSelected,
  } = useMangaSelection();

  // Release one API request at a time so a cold page can reuse the first
  // Lambda environment instead of creating a startup burst.
  const authRequestsInFlight = useIsFetching({
    queryKey: ["me"],
    exact: true,
  });
  const [primaryRequestReleased, setPrimaryRequestReleased] = useState(
    authRequestsInFlight === 0,
  );

  useEffect(() => {
    if (authRequestsInFlight === 0) {
      setPrimaryRequestReleased(true);
    }
  }, [authRequestsInFlight]);

  const params = useMemo(
    () => ({
      title,
      page,
      size: 25,
      genre_ids: genreSelection.includedIds,
      exclude_genres: genreSelection.excludedIds,
      tag_ids: tagSelection.includedIds,
      exclude_tags: tagSelection.excludedIds,
      demo_ids: demoSelection.includedIds,
      exclude_demos: demoSelection.excludedIds,
      match_mode: matchMode,
      order_by: "title" as const,
      order_dir: "asc" as const,
    }),
    [title, page, genreSelection, tagSelection, demoSelection, matchMode],
  );

  const mangaQ = useQuery<MangaSearchResponse>({
    queryKey: ["mangas", params],
    queryFn: ({ signal }) => searchMangas(params, signal),
    placeholderData: keepPreviousData,
    staleTime: 60_000,
    enabled: primaryRequestReleased,
  });

  const [secondaryRequestsReleased, setSecondaryRequestsReleased] = useState(false);

  useEffect(() => {
    if (mangaQ.isFetched && !mangaQ.isFetching) {
      setSecondaryRequestsReleased(true);
    }
  }, [mangaQ.isFetched, mangaQ.isFetching]);

  const meQ = useMe(secondaryRequestsReleased);
  const authSettled = secondaryRequestsReleased && !meQ.isPending && !meQ.isFetching;
  const isAuthenticated = Boolean(meQ.data);

  const genresQ = useQuery({
    queryKey: ["genres"],
    queryFn: getGenres,
    staleTime: 10 * 60_000,
    enabled: authSettled,
  });
  const genresSettled = authSettled && !genresQ.isPending && !genresQ.isFetching;

  const demosQ = useQuery({
    queryKey: ["demographics"],
    queryFn: getDemographics,
    staleTime: 10 * 60_000,
    enabled: genresSettled,
  });
  const demosSettled = genresSettled && !demosQ.isPending && !demosQ.isFetching;

  const tagsRequested =
    tagFilterActivated ||
    tagSelection.includedIds.length > 0 ||
    tagSelection.excludedIds.length > 0;
  const tagsQ = useQuery({
    queryKey: ["tags"],
    queryFn: getTags,
    staleTime: 10 * 60_000,
    enabled: demosSettled && tagsRequested,
  });

  function handleGetRecommendations() {
    if (selectedIds.length === 0) return;

    try {
      sessionStorage.setItem("recommendationSeedIds", JSON.stringify(selectedIds));
    } catch {
      // ignore storage failure
    }

    nav("/recommendations", {
      state: {
        mangaIds: selectedIds,
      },
    });
  }

  function handleOpenAddToCollection() {
    setBulkAddFeedback(null);

    if (!isAuthenticated) {
      setIsAuthRequiredModalOpen(true);
      return;
    }

    setIsCollectionModalOpen(true);
  }

  async function handleConfirmAddToCollection(collectionId: number) {
    setBulkAddFeedback(null);
    setIsBulkAdding(true);

    try {
      const result = await addMangasBulkToCollection(collectionId, selectedIds);

      await qc.invalidateQueries({ queryKey: ["collections", "list"] });
      await qc.invalidateQueries({ queryKey: ["collections", "detail", collectionId] });
      await qc.invalidateQueries({ queryKey: ["collections", "mangas", collectionId] });

      if (result.added_count > 0) {
        await qc.invalidateQueries({
          queryKey: recommendationKeys.collections,
        });
      }

      setIsCollectionModalOpen(false);

      if (result.added_count > 0) {
        removeSelectedIds(result.added_ids);
      }

      const alreadyExistsCount = result.failed.filter(
        (failure) => failure.reason === "ALREADY_EXISTS",
      ).length;

      const collectionMissingCount = result.failed.filter(
        (failure) => failure.reason === "COLLECTION_NOT_FOUND",
      ).length;

      const unknownFailureCount = result.failed.filter(
        (failure) => failure.reason === "UNKNOWN",
      ).length;

      const summaryParts: string[] = [];

      if (alreadyExistsCount > 0) {
        summaryParts.push(`${alreadyExistsCount} already in the collection`);
      }

      if (collectionMissingCount > 0) {
        summaryParts.push(
          `${collectionMissingCount} failed because the collection was not found`,
        );
      }

      if (unknownFailureCount > 0) {
        summaryParts.push(`${unknownFailureCount} failed for another reason`);
      }

      const summaryDetail = summaryParts.length > 0 ? ` ${summaryParts.join("; ")}.` : "";

      if (result.added_count > 0 && result.failed_count === 0) {
        setBulkAddFeedback(`${result.added_count} manga added to collection.`);
        return;
      }

      if (result.added_count > 0 && result.failed_count > 0) {
        setBulkAddFeedback(
          `${result.added_count} manga added, ${result.failed_count} failed.${summaryDetail}`,
        );
        return;
      }

      setBulkAddFeedback(`No manga were added.${summaryDetail}`);
    } finally {
      setIsBulkAdding(false);
    }
  }

  const updateParams = useCallback(
    (updates: Record<string, SearchParamValue>, options: { replace?: boolean } = {}) => {
      const next = new URLSearchParams(searchParams);

      for (const [key, value] of Object.entries(updates)) {
        if (Array.isArray(value)) {
          next.delete(key);
          for (const item of value) {
            next.append(key, String(item));
          }
          continue;
        }

        if (value === null || value === undefined || value === "") {
          next.delete(key);
        } else {
          next.set(key, String(value));
        }
      }

      setSearchParams(next, { replace: options.replace ?? false });
    },
    [searchParams, setSearchParams],
  );

  useEffect(() => {
    setTitleInput(title);
  }, [title]);

  useEffect(() => {
    const nextTitle = titleInput.trim();

    if (nextTitle === title.trim()) return;

    const timeoutId = window.setTimeout(() => {
      updateParams(
        {
          title: nextTitle || null,
          page: 1,
        },
        { replace: true },
      );
    }, SEARCH_DEBOUNCE_MS);

    return () => window.clearTimeout(timeoutId);
  }, [title, titleInput, updateParams]);

  const total = mangaQ.data?.total_results ?? 0;
  const size = mangaQ.data?.size ?? 25;
  const totalPages = Math.max(1, Math.ceil(total / size));
  const primaryRequestPending = !primaryRequestReleased || mangaQ.isLoading;
  const resultsAreUpdating =
    titleInput.trim() !== title.trim() || (mangaQ.isFetching && !mangaQ.isLoading);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-semibold">Search</h1>
        <p className="mt-1 text-sm opacity-80">Browse manga by title and filters.</p>
      </div>

      {/* Selection Summary Bar */}
      <SearchSelectionBar
        selectedCount={selectedCount}
        onClear={clearSelection}
        onGetRecommendations={handleGetRecommendations}
        onAddToCollection={handleOpenAddToCollection}
        canAddToCollection={isAuthenticated}
      />

      {bulkAddFeedback && (
        <div className="rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm">
          {bulkAddFeedback}
        </div>
      )}

      <AuthRequiredModal
        open={isAuthRequiredModalOpen}
        onClose={() => setIsAuthRequiredModalOpen(false)}
        title="Sign in required"
        message="You need an account to save manga to a collection."
      />

      <CollectionPickerModal
        open={isCollectionModalOpen}
        onClose={() => setIsCollectionModalOpen(false)}
        onConfirm={handleConfirmAddToCollection}
        isSubmitting={isBulkAdding}
        selectedCount={selectedCount}
      />

      {/* Filters */}
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-5">
        <div className="md:col-span-2 lg:col-span-2">
          <label className="mb-1 block text-sm">Title</label>
          <input
            className="w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2"
            placeholder="e.g. Naruto"
            value={titleInput}
            onChange={(e) => {
              const nextTitle = e.target.value;
              setTitleInput(nextTitle);

              if (!nextTitle.trim()) {
                updateParams(
                  {
                    title: null,
                    page: 1,
                  },
                  { replace: true },
                );
              }
            }}
            onKeyDown={(e) => {
              if (e.key !== "Enter") return;

              e.preventDefault();
              updateParams(
                {
                  title: titleInput.trim() || null,
                  page: 1,
                },
                { replace: true },
              );
            }}
          />
        </div>

        <MetadataMultiSelect
          label="Genre"
          placeholder="Any genre"
          searchable
          options={(genresQ.data ?? []).map((genre) => ({
            id: genre.genre_id,
            label: genre.genre_name,
          }))}
          includedIds={genreSelection.includedIds}
          excludedIds={genreSelection.excludedIds}
          isLoading={!authSettled || genresQ.isLoading}
          isError={genresQ.isError}
          onChange={({ includedIds, excludedIds }) => {
            updateParams({
              genre: includedIds,
              exclude_genre: excludedIds,
              page: 1,
            });
          }}
        />

        <MetadataMultiSelect
          label="Tag"
          placeholder="Any tag"
          searchable
          options={(tagsQ.data ?? []).map((tag) => ({
            id: tag.tag_id,
            label: tag.tag_name,
          }))}
          includedIds={tagSelection.includedIds}
          excludedIds={tagSelection.excludedIds}
          isLoading={tagsRequested && (!demosSettled || tagsQ.isLoading)}
          isError={tagsQ.isError}
          onActivate={() => setTagFilterActivated(true)}
          onChange={({ includedIds, excludedIds }) => {
            updateParams({
              tag: includedIds,
              exclude_tag: excludedIds,
              page: 1,
            });
          }}
        />

        <MetadataMultiSelect
          label="Demographic"
          placeholder="Any demographic"
          searchable
          options={(demosQ.data ?? []).map((demographic) => ({
            id: demographic.demographic_id,
            label: demographic.demographic_name,
          }))}
          includedIds={demoSelection.includedIds}
          excludedIds={demoSelection.excludedIds}
          isLoading={!genresSettled || demosQ.isLoading}
          isError={demosQ.isError}
          onChange={({ includedIds, excludedIds }) => {
            updateParams({
              demo: includedIds,
              exclude_demo: excludedIds,
              page: 1,
            });
          }}
        />

        <fieldset className="md:col-span-2 lg:col-span-5">
          <legend className="mb-1 text-sm">Match selected metadata</legend>
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm">
            <label className="flex items-center gap-2">
              <input
                type="radio"
                name="metadata-match-mode"
                value="and"
                checked={matchMode === "and"}
                onChange={() => updateParams({ match: null, page: 1 })}
              />
              All selected (AND)
            </label>
            <label className="flex items-center gap-2">
              <input
                type="radio"
                name="metadata-match-mode"
                value="or"
                checked={matchMode === "or"}
                onChange={() => updateParams({ match: "or", page: 1 })}
              />
              Any selected (OR)
            </label>
            <span className="text-xs text-neutral-400">
              AND requires every included selection; OR requires at least one. Exclusions
              always apply.
            </span>
          </div>
        </fieldset>
      </div>

      {/* Loading States*/}
      {(genresQ.isLoading || demosQ.isLoading) && (
        <div className="text-sm opacity-80">Loading filters…</div>
      )}

      {primaryRequestPending && (
        <div aria-live="polite" aria-busy="true" className="space-y-3">
          <div className="text-sm opacity-80">Loading results…</div>
          <div
            aria-hidden="true"
            className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5"
          >
            {Array.from({ length: 10 }, (_, index) => (
              <div
                key={index}
                className="overflow-hidden rounded-xl border border-neutral-800 bg-neutral-900"
              >
                <div className="aspect-[2/3] animate-pulse bg-neutral-800" />
                <div className="min-h-[72px] p-3">
                  <div className="h-4 w-3/4 animate-pulse rounded bg-neutral-800" />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {mangaQ.isError && (
        <div className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">
          {(mangaQ.error as Error)?.message ?? "Failed to load manga."}
        </div>
      )}

      {/* Results Section */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-sm opacity-80">
          <span>
            {total.toLocaleString()} result{total === 1 ? "" : "s"}
            {resultsAreUpdating && (
              <span role="status" className="ml-2">
                Updating…
              </span>
            )}
          </span>
          <span>
            Page {page} / {totalPages}
          </span>
        </div>

        {/* Manga Grid */}
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
          {(mangaQ.data?.items ?? []).map((manga) => (
            <MangaCard
              key={manga.manga_id}
              manga={manga}
              selectable
              selected={isSelected(manga.manga_id)}
              onToggleSelect={toggleSelection}
            />
          ))}
        </div>

        {/* Empty State */}
        {!primaryRequestPending && (mangaQ.data?.items?.length ?? 0) === 0 && (
          <div className="text-sm opacity-80">No results.</div>
        )}
      </div>

      {/* Pagination */}
      <div className="flex items-center gap-3">
        <button
          className="rounded-md border border-neutral-700 px-3 py-2 disabled:opacity-50"
          disabled={page <= 1 || primaryRequestPending}
          onClick={() => updateParams({ page: Math.max(1, page - 1) })}
        >
          Prev
        </button>

        <button
          className="rounded-md border border-neutral-700 px-3 py-2 disabled:opacity-50"
          disabled={page >= totalPages || primaryRequestPending}
          onClick={() => updateParams({ page: Math.min(totalPages, page + 1) })}
        >
          Next
        </button>
      </div>
    </div>
  );
}
