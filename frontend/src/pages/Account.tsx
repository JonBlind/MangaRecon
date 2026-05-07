import { useState } from "react";
import { useMe } from "../hooks/useMe";
import { useUpdateProfile } from "../hooks/useProfile";

export default function Account() {
  const meQ = useMe();
  const updateMutation = useUpdateProfile();

  const [displayName, setDisplayName] = useState("");

  if (meQ.isLoading) {
    return <div className="text-sm opacity-80">Loading account…</div>;
  }

  if (!meQ.data) {
    return <div className="text-sm">Not authenticated.</div>;
  }

  const user = meQ.data;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    await updateMutation.mutateAsync({
      displayname: displayName,
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
            placeholder={user.displayname ?? ""}
          />
        </div>

        <button
          type="submit"
          className="rounded-md border border-neutral-700 px-3 py-2 text-sm hover:bg-neutral-800"
          disabled={updateMutation.isPending}
        >
          {updateMutation.isPending ? "Saving..." : "Save"}
        </button>
      </form>

      {updateMutation.isSuccess && (
        <div className="text-sm text-green-400">Profile updated.</div>
      )}

      {updateMutation.isError && (
        <div className="text-sm text-red-400">
          Failed to update profile.
        </div>
      )}
    </div>
  );
}