import { apiFetch } from "./http";

export async function updateProfile(payload: {
  displayname: string;
}) {
  const res = await apiFetch<null>("/profiles/me", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });

  return res;
}