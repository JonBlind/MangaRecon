import { useEffect, useState } from "react";
import { useMe } from "../hooks/useMe";
import { useUpdateProfile } from "../hooks/useProfile";
import { ApiRequestError } from "../api/http";

export default function Account() {
  const meQ = useMe();
  const updateMutation = useUpdateProfile();

  const [displayName, setDisplayName] = useState("");

  useEffect(() => {
    if (meQ.data) {
      setDisplayName(meQ.data.displayname ?? "");
    }
  }, [meQ.data]);

  if (meQ.isLoading) {
    return <div className="text-sm opacity-80">Loading account…</div>;
  }

  if (!meQ.data) {
    return <div className="text-sm">Not authenticated.</div>;
  }

  const user = meQ.data;
  const trimmedDisplayName = displayName.trim();
  const isUnchanged = trimmedDisplayName === user.displayname;
  const canSave =
    trimmedDisplayName.length > 0 &&
    !isUnchanged &&
    !updateMutation.isPending;

  const errorMsg =
    updateMutation.error instanceof ApiRequestError
      ? updateMutation.error.message
      : updateMutation.error
        ? "Failed to update profile."
        : null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    if (!canSave) return;

    await updateMutation.mutateAsync({
      displayname: trimmedDisplayName,
    });
  }

  return (
    <div className="space-y-6 max-w-xl">
      <h1 className="text-3xl font-semibold">Account</h1>

      <div className="space-y-2 text-sm">
        <div>
          <span className="opacity-70">Username:</span> {user.username}
        </div>
        <div>
          <span className="opacity-70">Email:</span> {user.email}
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-3">
        <div>
          <label className="block text-sm mb-1">Display Name</label>
          <input
            className="w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
          />
        </div>

        <button
          type="submit"
          className="rounded-md border border-neutral-700 px-3 py-2 text-sm hover:bg-neutral-800 disabled:opacity-50"
          disabled={!canSave}
        >
          {updateMutation.isPending ? "Saving..." : "Save"}
        </button>
      </form>

      {updateMutation.isSuccess && (
        <div className="text-sm text-green-400">Profile updated.</div>
      )}

      {errorMsg && (
        <div className="text-sm text-red-400">{errorMsg}</div>
      )}
    </div>
  );
}