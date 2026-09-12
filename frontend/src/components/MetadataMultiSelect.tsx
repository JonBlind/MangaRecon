import { useEffect, useId, useMemo, useRef, useState } from "react";

const MAX_VISIBLE_OPTIONS = 50;

export type MetadataOption = {
  id: number;
  label: string;
};

export type MetadataSelection = {
  includedIds: number[];
  excludedIds: number[];
};

type MetadataMultiSelectProps = {
  label: string;
  options: MetadataOption[];
  includedIds: number[];
  excludedIds: number[];
  placeholder: string;
  isLoading: boolean;
  isError: boolean;
  searchable?: boolean;
  onActivate?: () => void;
  onChange: (selection: MetadataSelection) => void;
};

export default function MetadataMultiSelect({
  label,
  options,
  includedIds,
  excludedIds,
  placeholder,
  isLoading,
  isError,
  searchable = false,
  onActivate,
  onChange,
}: MetadataMultiSelectProps) {
  const panelId = useId();
  const containerRef = useRef<HTMLDivElement>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");

  const sortedOptions = useMemo(
    () => [...options].sort((a, b) => a.label.localeCompare(b.label)),
    [options],
  );

  const visibleOptions = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase();
    const matches = normalizedQuery
      ? sortedOptions.filter((option) =>
          option.label.toLocaleLowerCase().includes(normalizedQuery),
        )
      : sortedOptions;

    return matches.slice(0, MAX_VISIBLE_OPTIONS);
  }, [query, sortedOptions]);

  const selectionSummary = useMemo(() => {
    const summaryParts: string[] = [];

    if (includedIds.length > 0) {
      summaryParts.push(`${includedIds.length} included`);
    }
    if (excludedIds.length > 0) {
      summaryParts.push(`${excludedIds.length} excluded`);
    }

    return summaryParts.length > 0 ? summaryParts.join(" · ") : placeholder;
  }, [excludedIds.length, includedIds.length, placeholder]);

  useEffect(() => {
    if (!isOpen) return;

    function handlePointerDown(event: PointerEvent) {
      if (!containerRef.current?.contains(event.target as Node)) {
        setIsOpen(false);
        setQuery("");
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsOpen(false);
        setQuery("");
      }
    }

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  function cycleOption(optionId: number) {
    if (includedIds.includes(optionId)) {
      onChange({
        includedIds: includedIds.filter((id) => id !== optionId),
        excludedIds: [...excludedIds.filter((id) => id !== optionId), optionId],
      });
      return;
    }

    if (excludedIds.includes(optionId)) {
      onChange({
        includedIds: includedIds.filter((id) => id !== optionId),
        excludedIds: excludedIds.filter((id) => id !== optionId),
      });
      return;
    }

    onChange({
      includedIds: [...includedIds, optionId],
      excludedIds,
    });
  }

  return (
    <div ref={containerRef} className="relative">
      <span className="mb-1 block text-sm">{label}</span>
      <button
        type="button"
        aria-label={`${label} filter`}
        aria-expanded={isOpen}
        aria-controls={panelId}
        className="flex w-full items-center justify-between gap-2 rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-left"
        onClick={() => {
          const nextIsOpen = !isOpen;
          setIsOpen(nextIsOpen);
          if (nextIsOpen) onActivate?.();
          if (!nextIsOpen) setQuery("");
        }}
      >
        <span
          className={
            includedIds.length === 0 && excludedIds.length === 0
              ? "text-neutral-400"
              : undefined
          }
        >
          {selectionSummary}
        </span>
        <span aria-hidden="true" className="text-neutral-400">
          {isOpen ? "▴" : "▾"}
        </span>
      </button>

      {isOpen && (
        <div
          id={panelId}
          className="absolute z-30 mt-1 w-full min-w-56 rounded-md border border-neutral-700 bg-neutral-900 p-2 shadow-xl"
        >
          {searchable && (
            <input
              type="search"
              aria-label={`Search ${label.toLowerCase()} options`}
              autoComplete="off"
              className="mb-2 w-full rounded-md border border-neutral-700 bg-neutral-950 px-3 py-2 text-sm"
              placeholder={`Search ${label.toLowerCase()}s`}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          )}

          <p className="mb-2 text-xs text-neutral-400">
            Press once to include, twice to exclude, and three times to clear.
          </p>

          {includedIds.length + excludedIds.length > 0 && (
            <button
              type="button"
              className="mb-2 text-xs text-neutral-300 underline hover:text-white"
              onClick={() => onChange({ includedIds: [], excludedIds: [] })}
            >
              Clear all
            </button>
          )}

          <div className="max-h-64 overflow-y-auto">
            {isLoading ? (
              <div className="px-2 py-1 text-sm text-neutral-400">
                Loading {label.toLowerCase()}s…
              </div>
            ) : isError ? (
              <div className="px-2 py-1 text-sm text-red-300">
                Couldn&apos;t load {label.toLowerCase()}s.
              </div>
            ) : visibleOptions.length === 0 ? (
              <div className="px-2 py-1 text-sm text-neutral-400">
                No matching {label.toLowerCase()}s.
              </div>
            ) : (
              <div role="group" aria-label={`${label} options`}>
                {visibleOptions.map((option) => {
                  const isIncluded = includedIds.includes(option.id);
                  const isExcluded = !isIncluded && excludedIds.includes(option.id);
                  const stateLabel = isIncluded
                    ? "Included"
                    : isExcluded
                      ? "Excluded"
                      : "Not selected";

                  return (
                    <button
                      key={option.id}
                      type="button"
                      role="checkbox"
                      aria-checked={isIncluded ? true : isExcluded ? "mixed" : false}
                      aria-label={`${option.label}: ${stateLabel}`}
                      title={
                        isIncluded
                          ? `Exclude ${option.label}`
                          : isExcluded
                            ? `Clear ${option.label}`
                            : `Include ${option.label}`
                      }
                      className="flex w-full cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-left text-sm hover:bg-neutral-800"
                      onClick={() => cycleOption(option.id)}
                    >
                      <span
                        aria-hidden="true"
                        className={[
                          "flex h-4 w-4 shrink-0 items-center justify-center rounded border text-xs font-bold",
                          isIncluded
                            ? "border-emerald-400 bg-emerald-400 text-neutral-950"
                            : isExcluded
                              ? "border-red-400 bg-red-400 text-neutral-950"
                              : "border-neutral-500",
                        ].join(" ")}
                      >
                        {isIncluded ? "✓" : isExcluded ? "×" : ""}
                      </span>
                      <span className="min-w-0 flex-1">{option.label}</span>
                      {(isIncluded || isExcluded) && (
                        <span
                          className={
                            isIncluded
                              ? "text-xs text-emerald-300"
                              : "text-xs text-red-300"
                          }
                        >
                          {stateLabel}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
