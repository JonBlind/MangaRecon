import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  useCollections,
  useCreateCollection,
  useDeleteCollection,
} from "../hooks/useCollections";

export default function Collections() {
  const nav = useNavigate();

  // Paging
  const [page, setPage] = useState(1);

  // Create form
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");

  const params = useMemo(
    () => ({
      page,
      size: 20,
      order: "desc" as const,
    }),
    [page]
  );

  const listQ = useCollections(params);
  const createM = useCreateCollection();
  const deleteM = useDeleteCollection();

  const total = listQ.data?.total_results ?? 0;
  const size = listQ.data?.size ?? 20;
  const totalPages = Math.max(1, Math.ceil(total / size));

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();

    const trimmedName = name.trim();
    const trimmedDesc = desc.trim();

    if (!trimmedName) return;

    try {
      const created = await createM.mutateAsync({
        collection_name: trimmedName,
        description: trimmedDesc ? trimmedDesc : null,
      });

      // Reset UI
      setName("");
      setDesc("");
      setShowCreate(false);

      // Navigate to the newly created collection
      nav(`/collections/${created.collection_id}`);
    } catch {
      // error rendered below
    }
  }

  async function handleDelete(collectionId: number, collectionName: string) {
    const ok = window.confirm(
      `Delete collection "${collectionName}"?\n\nThis cannot be undone.`
    );
    if (!ok) return;

    try {
      await deleteM.mutateAsync(collectionId);
      // Keep user on a valid page if they delete last item on a page
      // (simple heuristic: if page > 1 and this was the last item, go back a page)
      const itemsOnPage = listQ.data?.items?.length ?? 0;
      if (page > 1 && itemsOnPage === 1) setPage((p) => Math.max(1, p - 1));
    } catch {
      // error rendered below
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold">Collections</h1>
          <p className="mt-1 text-sm opacity-80">
            Create lists to organize manga and power recommendations later.
          </p>
        </div>

        <button
          className="rounded-md border border-neutral-700 px-4 py-2 hover:bg-neutral-900"
          onClick={() => setShowCreate((v) => !v)}
        >
          {showCreate ? "Cancel" : "New collection"}
        </button>
      </div>

      {/* Create form */}
      {showCreate && (
        <form
          onSubmit={handleCreate}
          className="rounded-xl border border-neutral-800 bg-neutral-900 p-4"
        >
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <div>
              <label className="mb-1 block text-sm">Name</label>
              <input
                className="w-full rounded-md border border-neutral-700 bg-neutral-950 px-3 py-2"
                placeholder="e.g. Favorites, To Read, Psychological Thrillers…"
                value={name}
                onChange={(e) => setName(e.target.value)}
                maxLength={80}
                autoFocus
              />
              <div className="mt-1 text-xs opacity-60">{name.trim().length}/80</div>
            </div>

            <div>
              <label className="mb-1 block text-sm">Description (optional)</label>
              <input
                className="w-full rounded-md border border-neutral-700 bg-neutral-950 px-3 py-2"
                placeholder="Short note about this collection"
                value={desc}
                onChange={(e) => setDesc(e.target.value)}
                maxLength={200}
              />
              <div className="mt-1 text-xs opacity-60">{desc.trim().length}/200</div>
            </div>
          </div>

          {(createM.isError && (
            <div className="mt-3 rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">
              {(createM.error as any)?.message ?? "Failed to create collection."}
            </div>
          )) ||
            null}

          <div className="mt-4 flex items-center gap-3">
            <button
              className="rounded-md border border-neutral-700 px-4 py-2 hover:bg-neutral-800 disabled:opacity-50"
              type="submit"
              disabled={!name.trim() || createM.isPending}
            >
              {createM.isPending ? "Creating…" : "Create"}
            </button>
            <span className="text-sm opacity-70">
              Collections are private to your account.
            </span>
          </div>
        </form>
      )}

      {/* Status */}
      {listQ.isLoading && <div className="text-sm opacity-80">Loading collections…</div>}

      {listQ.isError && (
        <div className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">
          {(listQ.error as any)?.message ?? "Failed to load collections."}
        </div>
      )}

      {deleteM.isError && (
        <div className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">
          {(deleteM.error as any)?.message ?? "Failed to delete collection."}
        </div>
      )}

      {/* List */}
      {!listQ.isLoading && !listQ.isError && (
        <div className="space-y-3">
          <div className="flex items-center justify-between text-sm opacity-80">
            <span>
              {total.toLocaleString()} collection{total === 1 ? "" : "s"}
            </span>
            <span>
              Page {page} / {totalPages}
            </span>
          </div>

          <div className="grid grid-cols-1 gap-3">
            {(listQ.data?.items ?? []).map((c) => (
              <div
                key={c.collection_id}
                className="group rounded-xl border border-neutral-800 bg-neutral-900 p-4 transition hover:border-neutral-600"
                role="button"
                tabIndex={0}
                onClick={() => nav(`/collections/${c.collection_id}`)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    nav(`/collections/${c.collection_id}`);
                  }
                }}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="truncate text-lg font-semibold">
                      {c.collection_name}
                    </div>
                    {c.description ? (
                      <div className="mt-1 line-clamp-2 text-sm opacity-80">
                        {c.description}
                      </div>
                    ) : (
                      <div className="mt-1 text-sm opacity-60">
                        No description
                      </div>
                    )}
                    <div className="mt-2 text-xs opacity-60">
                      Created {new Date(c.created_at).toLocaleString()}
                    </div>
                  </div>

                  <button
                    className="rounded-md border border-neutral-700 px-3 py-2 text-sm opacity-90 hover:bg-neutral-950 hover:opacity-100 disabled:opacity-50"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDelete(c.collection_id, c.collection_name);
                    }}
                    disabled={deleteM.isPending}
                    title="Delete collection"
                  >
                    {deleteM.isPending ? "Deleting…" : "Delete"}
                  </button>
                </div>
              </div>
            ))}

            {(listQ.data?.items?.length ?? 0) === 0 && (
              <div className="rounded-xl border border-neutral-800 bg-neutral-900 p-6 text-sm opacity-80">
                No collections yet. Create your first one to start organizing manga.
              </div>
            )}
          </div>

          {/* Paging */}
          <div className="flex items-center gap-3 pt-2">
            <button
              className="rounded-md border border-neutral-700 px-3 py-2 disabled:opacity-50"
              disabled={page <= 1 || listQ.isFetching}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              Prev
            </button>

            <button
              className="rounded-md border border-neutral-700 px-3 py-2 disabled:opacity-50"
              disabled={page >= totalPages || listQ.isFetching}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
