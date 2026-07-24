import { useEffect, useState, type FormEvent} from "react";
import { ApiRequestError } from "../api/http";
import { useMe } from "../hooks/useMe";
import { useUpdateProfile } from "../hooks/useProfile";

const MIN_PROFILE_FIELD_LENGTH = 4;
const MAX_PROFILE_FIELD_LENGTH = 64;
const USERNAME_COOLDOWN_MS = 30 * 24 * 60 * 60 * 1000;

function getNextUsernameChangeAt(
  usernameChangedAt: string | null | undefined,
): Date | null {
  if (!usernameChangedAt) {
    return null;
  }

  const changedAtMs = Date.parse(usernameChangedAt);

  if (Number.isNaN(changedAtMs)) {
    return null;
  }

  return new Date(changedAtMs + USERNAME_COOLDOWN_MS);
}

export default function Account() {
  const meQ = useMe();
  const updateMutation = useUpdateProfile();

  const [displayName, setDisplayName] =
    useState("");
  const [username, setUsername] = useState("");

  const [
    isEditingUsername,
    setIsEditingUsername,
  ] = useState(false);

  const [
    isConfirmingUsernameChange,
    setIsConfirmingUsernameChange,
  ] = useState(false);

  useEffect(() => {
    if (!meQ.data) {
      return;
    }

    setDisplayName(meQ.data.displayname ?? "");
    setUsername(meQ.data.username ?? "");
  }, [meQ.data]);

  if (meQ.isLoading) {
    return (
      <div className="text-sm opacity-80">
        Loading account…
      </div>
    );
  }

  if (!meQ.data) {
    return (
      <div className="text-sm">
        Not authenticated.
      </div>
    );
  }

  const user = meQ.data;

  const nextUsernameChangeAt =
    getNextUsernameChangeAt(
      user.username_changed_at,
    );

  const usernameIsOnCooldown =
    nextUsernameChangeAt !== null &&
    nextUsernameChangeAt.getTime() > Date.now();

  const nextUsernameChangeLabel =
    nextUsernameChangeAt?.toLocaleString(
      undefined,
      {
        year: "numeric",
        month: "long",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
      },
    );

  const trimmedDisplayName =
    displayName.trim();
  const trimmedUsername = username.trim();

  const displayNameChanged =
    trimmedDisplayName !== user.displayname;

  const usernameChanged =
    isEditingUsername &&
    trimmedUsername !== user.username;

  const displayNameIsValid =
    trimmedDisplayName.length >=
      MIN_PROFILE_FIELD_LENGTH &&
    trimmedDisplayName.length <=
      MAX_PROFILE_FIELD_LENGTH;

  const usernameIsValid =
    !isEditingUsername ||
    (trimmedUsername.length >=
      MIN_PROFILE_FIELD_LENGTH &&
      trimmedUsername.length <=
        MAX_PROFILE_FIELD_LENGTH);

  const hasChanges =
    displayNameChanged || usernameChanged;

  const canSave =
    hasChanges &&
    displayNameIsValid &&
    usernameIsValid &&
    (!usernameChanged ||
      !usernameIsOnCooldown) &&
    !updateMutation.isPending;

  const errorMsg =
    updateMutation.error instanceof
    ApiRequestError
      ? updateMutation.error.message
      : updateMutation.error
        ? "Failed to update profile."
        : null;

  function beginUsernameEdit() {
    if (usernameIsOnCooldown) {
      return;
    }

    updateMutation.reset();
    setUsername(user.username);
    setIsEditingUsername(true);
    setIsConfirmingUsernameChange(false);
  }

  function cancelUsernameEdit() {
    updateMutation.reset();
    setUsername(user.username);
    setIsEditingUsername(false);
    setIsConfirmingUsernameChange(false);
  }

  async function handleSubmit(
    e: FormEvent<HTMLFormElement>,
  ) {
    e.preventDefault();

    if (!canSave) {
      return;
    }

    if (
      usernameChanged &&
      !isConfirmingUsernameChange
    ) {
      setIsConfirmingUsernameChange(true);
      return;
    }

    const payload: {
      username?: string;
      displayname?: string;
    } = {};

    if (displayNameChanged) {
      payload.displayname =
        trimmedDisplayName;
    }

    if (usernameChanged) {
      payload.username = trimmedUsername;
    }

    try {
      await updateMutation.mutateAsync(
        payload,
      );

      setIsEditingUsername(false);
      setIsConfirmingUsernameChange(
        false,
      );
    } catch {
      // The mutation exposes its error through
      // updateMutation.error.
    }
  }

  return (
    <div className="max-w-xl space-y-8">
      <h1 className="text-3xl font-semibold">
        Account
      </h1>

      <section className="space-y-2">
        <h2 className="text-lg font-medium">
          Account information
        </h2>

        <div className="text-sm">
          <span className="opacity-70">
            Email:
          </span>{" "}
          {user.email}
        </div>
      </section>

      <form
        onSubmit={handleSubmit}
        className="space-y-6"
      >
        <section className="space-y-3">
          <div>
            <label
              htmlFor="displayName"
              className="mb-1 block text-sm font-medium"
            >
              Display name
            </label>

            <p className="mb-2 text-xs opacity-70">
              This is the name other users
              will see. You may change it at
              any time.
            </p>

            <input
              id="displayName"
              className="w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2"
              value={displayName}
              maxLength={
                MAX_PROFILE_FIELD_LENGTH
              }
              onChange={(e) => {
                updateMutation.reset();
                setDisplayName(e.target.value);
              }}
            />

            {trimmedDisplayName.length > 0 &&
              !displayNameIsValid && (
                <p className="mt-1 text-xs text-red-400">
                  Display name must be between
                  4 and 64 characters.
                </p>
              )}
          </div>
        </section>

        <section className="space-y-3 border-t border-neutral-800 pt-5">
          <div>
            <div className="flex items-center justify-between gap-4">
              <div>
                <label
                  htmlFor="username"
                  className="block text-sm font-medium"
                >
                  Username
                </label>

                <p className="mt-1 text-xs opacity-70">
                  Your unique account
                  identifier. It can only be
                  changed once every 30 days.
                </p>
              </div>

              {!isEditingUsername && (
                <button
                  type="button"
                  className="rounded-md border border-neutral-700 px-3 py-1.5 text-sm hover:bg-neutral-800 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent"
                  onClick={
                    beginUsernameEdit
                  }
                  disabled={
                    usernameIsOnCooldown
                  }
                >
                  {usernameIsOnCooldown
                    ? "Username change unavailable"
                    : "Change username"}
                </button>
              )}
            </div>

            {isEditingUsername ? (
              <div className="mt-3 space-y-2">
                <input
                  id="username"
                  className="w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2"
                  value={username}
                  maxLength={
                    MAX_PROFILE_FIELD_LENGTH
                  }
                  onChange={(e) => {
                    updateMutation.reset();
                    setUsername(
                      e.target.value,
                    );
                    setIsConfirmingUsernameChange(
                      false,
                    );
                  }}
                />

                <p className="text-xs text-amber-300">
                  Usernames are unique.
                  Changing yours may make it
                  harder for people to
                  recognize or find your
                  account.
                </p>

                {trimmedUsername.length >
                  0 &&
                  !usernameIsValid && (
                    <p className="text-xs text-red-400">
                      Username must be
                      between 4 and 64
                      characters.
                    </p>
                  )}

                <button
                  type="button"
                  className="text-sm opacity-70 hover:opacity-100 disabled:opacity-50"
                  onClick={
                    cancelUsernameEdit
                  }
                  disabled={
                    updateMutation.isPending
                  }
                >
                  Cancel username change
                </button>
              </div>
            ) : (
              <div className="mt-2 text-sm">
                {user.username}
              </div>
            )}

            {usernameIsOnCooldown &&
              nextUsernameChangeLabel && (
                <p className="mt-2 text-xs text-amber-300">
                  You can change your
                  username again on{" "}
                  {nextUsernameChangeLabel}.
                </p>
              )}
          </div>
        </section>

        {isConfirmingUsernameChange &&
          usernameChanged && (
            <div className="space-y-3 rounded-md border border-amber-700/60 bg-amber-950/20 p-4">
              <p className="text-sm font-medium">
                Confirm username change
              </p>

              <p className="text-sm opacity-80">
                Your username will change
                from{" "}
                <strong>
                  {user.username}
                </strong>{" "}
                to{" "}
                <strong>
                  {trimmedUsername}
                </strong>
                .
              </p>

              <p className="text-xs text-amber-300">
                After saving, you will not
                be able to change your
                username again for 30 days.
              </p>

              <p className="text-xs opacity-70">
                Select “Confirm and save” to
                apply this change.
              </p>
            </div>
          )}

        <button
          type="submit"
          className="rounded-md border border-neutral-700 px-3 py-2 text-sm hover:bg-neutral-800 disabled:cursor-not-allowed disabled:opacity-50"
          disabled={!canSave}
        >
          {updateMutation.isPending
            ? "Saving..."
            : usernameChanged &&
                isConfirmingUsernameChange
              ? "Confirm and save"
              : usernameChanged
                ? "Review changes"
                : "Save changes"}
        </button>
      </form>

      {updateMutation.isSuccess && (
        <div className="text-sm text-green-400">
          Profile updated.
        </div>
      )}

      {errorMsg && (
        <div className="text-sm text-red-400">
          {errorMsg}
        </div>
      )}
    </div>
  );
}