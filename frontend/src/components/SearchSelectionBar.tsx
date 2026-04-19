type SearchSelectionBarProps = {
  selectedCount: number;
  onClear: () => void;
  onGetRecommendations: () => void;
};

export default function SearchSelectionBar({
  selectedCount,
  onClear,
  onGetRecommendations,
}: SearchSelectionBarProps) {
  if (selectedCount <= 0) return null;

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-neutral-800 bg-neutral-900 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="text-sm">
        <span className="font-medium">{selectedCount}</span>{" "}
        selected
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          className="rounded-md border border-neutral-700 px-3 py-2 text-sm hover:bg-neutral-800"
          onClick={onClear}
        >
          Clear
        </button>

        <button
          type="button"
          className="rounded-md border border-neutral-700 px-3 py-2 text-sm hover:bg-neutral-800"
          onClick={onGetRecommendations}
        >
          Get Recommendations
        </button>
      </div>
    </div>
  );
}