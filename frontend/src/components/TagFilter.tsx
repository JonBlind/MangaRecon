import { useEffect, useId, useMemo, useState } from "react";
import type { Tag } from "../types/metadata";

const MAX_VISIBLE_TAGS = 50;

type TagFilterProps = {
  tags: Tag[];
  selectedTagId: number | "";
  isLoading: boolean;
  isError: boolean;
  onActivate: () => void;
  onChange: (tagId: number | "") => void;
};

export default function TagFilter({
  tags,
  selectedTagId,
  isLoading,
  isError,
  onActivate,
  onChange,
}: TagFilterProps) {
  const inputId = useId();
  const listboxId = useId();
  const [query, setQuery] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);

  const sortedTags = useMemo(
    () => [...tags].sort((a, b) => a.tag_name.localeCompare(b.tag_name)),
    [tags],
  );

  const selectedTag = useMemo(
    () => tags.find((tag) => tag.tag_id === selectedTagId),
    [selectedTagId, tags],
  );

  useEffect(() => {
    setQuery(selectedTag?.tag_name ?? "");
  }, [selectedTag]);

  const visibleTags = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase();
    const matches = normalizedQuery
      ? sortedTags.filter((tag) =>
          tag.tag_name.toLocaleLowerCase().includes(normalizedQuery),
        )
      : sortedTags;

    return matches.slice(0, MAX_VISIBLE_TAGS);
  }, [query, sortedTags]);

  const activeTag = visibleTags[activeIndex];

  function selectTag(tag: Tag) {
    setQuery(tag.tag_name);
    setIsOpen(false);
    setActiveIndex(0);
    onChange(tag.tag_id);
  }

  function clearTag() {
    setQuery("");
    setIsOpen(false);
    setActiveIndex(0);
    onChange("");
  }

  return (
    <div className="relative">
      <label htmlFor={inputId} className="mb-1 block text-sm">
        Tag
      </label>

      <div className="relative">
        <input
          id={inputId}
          type="search"
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={isOpen}
          aria-controls={listboxId}
          aria-activedescendant={
            isOpen && activeTag ? `${listboxId}-${activeTag.tag_id}` : undefined
          }
          autoComplete="off"
          className="w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 pr-9"
          placeholder="Any tag"
          value={query}
          onFocus={() => {
            onActivate();
            setIsOpen(true);
          }}
          onBlur={() => {
            setQuery(selectedTag?.tag_name ?? "");
            setIsOpen(false);
          }}
          onChange={(event) => {
            const nextQuery = event.target.value;
            setQuery(nextQuery);
            setIsOpen(true);
            setActiveIndex(0);
            onActivate();
          }}
          onKeyDown={(event) => {
            if (event.key === "ArrowDown") {
              event.preventDefault();
              setIsOpen(true);
              setActiveIndex((index) =>
                Math.min(index + 1, Math.max(visibleTags.length - 1, 0)),
              );
              return;
            }

            if (event.key === "ArrowUp") {
              event.preventDefault();
              setActiveIndex((index) => Math.max(index - 1, 0));
              return;
            }

            if (event.key === "Enter" && isOpen && activeTag) {
              event.preventDefault();
              selectTag(activeTag);
              return;
            }

            if (event.key === "Escape") {
              setIsOpen(false);
            }
          }}
        />

        {(query || selectedTagId !== "") && (
          <button
            type="button"
            aria-label="Clear tag filter"
            className="absolute inset-y-0 right-0 flex w-9 items-center justify-center text-neutral-400 hover:text-neutral-100"
            onPointerDown={(event) => event.preventDefault()}
            onClick={clearTag}
          >
            ×
          </button>
        )}
      </div>

      {isOpen && (
        <div className="absolute z-20 mt-1 max-h-64 w-full overflow-y-auto rounded-md border border-neutral-700 bg-neutral-900 shadow-xl">
          {isLoading ? (
            <div className="px-3 py-2 text-sm text-neutral-400">Loading tags…</div>
          ) : isError ? (
            <div className="px-3 py-2 text-sm text-red-300">Couldn&apos;t load tags.</div>
          ) : visibleTags.length === 0 ? (
            <div className="px-3 py-2 text-sm text-neutral-400">No matching tags.</div>
          ) : (
            <ul id={listboxId} role="listbox" aria-label="Tag suggestions">
              {visibleTags.map((tag, index) => (
                <li
                  key={tag.tag_id}
                  id={`${listboxId}-${tag.tag_id}`}
                  role="option"
                  aria-selected={tag.tag_id === selectedTagId}
                  className={[
                    "cursor-pointer px-3 py-2 text-sm",
                    index === activeIndex
                      ? "bg-neutral-700 text-white"
                      : "hover:bg-neutral-800",
                  ].join(" ")}
                  onPointerDown={(event) => {
                    event.preventDefault();
                    selectTag(tag);
                  }}
                  onMouseEnter={() => setActiveIndex(index)}
                >
                  {tag.tag_name}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
