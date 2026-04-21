import { useEffect, useState } from "react";
import { useCollections, useCreateCollection } from "../hooks/useCollections";

type CollectionPickerModalProps = {
  open: boolean;
  onClose: () => void;
  onConfirm: (collectionId: number) => void;
  isSubmitting?: boolean;
};

type Mode = "existing" | "create";

export default function CollectionPickerModal({
  open,
  onClose,
  onConfirm,
  isSubmitting = false,
}: CollectionPickerModalProps) {
  const { data, isLoading, isError } = useCollections({ page: 1, size: 100 });
  const createCollectionMutation = useCreateCollection();

  const [mode, setMode] = useState<Mode>("existing");
  const [selectedCollectionId, setSelectedCollectionId] = useState<number | "">("");
  const [newCollectionName, setNewCollectionName] = useState("");
  const [newCollectionDescription, setNewCollectionDescription] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setMode("existing");
      setSelectedCollectionId("");
      setNewCollectionName("");
      setNewCollectionDescription("");
      setLocalError(null);
    }
  }, [open]);

  if (!open) return null;

  const collections = data?.items ?? [];
  const isCreating = createCollectionMutation.isPending;
  const isBusy = isSubmitting || isCreating;

  async function handleConfirm() {
    setLocalError(null);

    try {
      if (mode === "existing") {
        if (selectedCollectionId === "") return;
        onConfirm(selectedCollectionId);
        return;
      }

      const name = newCollectionName.trim();
      const description = newCollectionDescription.trim();

      if (!name) {
        setLocalError("Collection name is required.");
        return;
      }

      const created = await createCollectionMutation.mutateAsync({
        collection_name: name,
        description: description || null,
      });

      onConfirm(created.collection_id);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Failed to create collection.";
      setLocalError(message);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={() => {
        if (!isBusy) {
          onClose();
        }
      }}
    >
      <div
        className="w-full max-w-md rounded-2xl border border-neutral-800 bg-neutral-950 p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-xl font-semibold">Add to Collection</h2>
        <p className="mt-1 text-sm opacity-80">
          Choose an existing collection or create a new one.
        </p>

        <div className="mt-4 flex items-center gap-2">
          <button
            type="button"
            className={`rounded-md border px-3 py-2 text-sm ${
              mode === "existing"
                ? "border-neutral-500 bg-neutral-800"
                : "border-neutral-700 hover:bg-neutral-900"
            }`}
            onClick={() => {
              setMode("existing");
              setLocalError(null);
            }}
            disabled={isBusy}
          >
            Use Existing
          </button>

          <button
            type="button"
            className={`rounded-md border px-3 py-2 text-sm ${
              mode === "create"
                ? "border-neutral-500 bg-neutral-800"
                : "border-neutral-700 hover:bg-neutral-900"
            }`}
            onClick={() => {
              setMode("create");
              setLocalError(null);
            }}
            disabled={isBusy}
          >
            Create New
          </button>
        </div>

        <div className="mt-4 space-y-3">
          {mode === "existing" ? (
            isLoading ? (
              <div className="text-sm opacity-80">Loading collections…</div>
            ) : isError ? (
              <div className="text-sm text-red-400">Failed to load collections.</div>
            ) : collections.length === 0 ? (
              <div className="text-sm opacity-80">No collections found. Create one instead.</div>
            ) : (
              <div>
                <label className="mb-1 block text-sm">Collection</label>
                <select
                  className="w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2"
                  value={selectedCollectionId}
                  onChange={(e) => {
                    const value = e.target.value;
                    setSelectedCollectionId(value === "" ? "" : Number(value));
                  }}
                  disabled={isBusy}
                >
                  <option value="">Select a collection</option>
                  {collections.map((collection) => (
                    <option
                      key={collection.collection_id}
                      value={collection.collection_id}
                    >
                      {collection.collection_name}
                    </option>
                  ))}
                </select>
              </div>
            )
          ) : (
            <>
              <div>
                <label className="mb-1 block text-sm">Collection Name</label>
                <input
                  className="w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2"
                  value={newCollectionName}
                  onChange={(e) => setNewCollectionName(e.target.value)}
                  placeholder="e.g. Mystery Favorites"
                  disabled={isBusy}
                />
              </div>

              <div>
                <label className="mb-1 block text-sm">Description</label>
                <textarea
                  className="w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2"
                  value={newCollectionDescription}
                  onChange={(e) => setNewCollectionDescription(e.target.value)}
                  placeholder="Optional description"
                  rows={3}
                  disabled={isBusy}
                />
              </div>
            </>
          )}

          {localError && (
            <div className="text-sm text-red-400">{localError}</div>
          )}
        </div>

        <div className="mt-6 flex items-center justify-end gap-2">
          <button
            type="button"
            className="rounded-md border border-neutral-700 px-3 py-2 text-sm hover:bg-neutral-900"
            onClick={onClose}
            disabled={isBusy}
          >
            Cancel
          </button>

          <button
            type="button"
            className="rounded-md border border-neutral-700 px-3 py-2 text-sm hover:bg-neutral-900 disabled:opacity-50"
            disabled={
              isBusy ||
              (mode === "existing" &&
                (isLoading || isError || selectedCollectionId === "")) ||
              (mode === "create" && newCollectionName.trim() === "")
            }
            onClick={handleConfirm}
          >
            {isSubmitting
              ? "Adding..."
              : isCreating
                ? "Creating..."
                : mode === "create"
                  ? "Create and Add"
                  : "Add"}
          </button>
        </div>
      </div>
    </div>
  );
}