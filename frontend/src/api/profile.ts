import { apiFetch } from "./http";
import type { UserMe } from "../types/auth";

export async function updateProfile(payload: {
  displayname: string;
}) {
  const res = await apiFetch<UserMe>("/profiles/me", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });

  return res;
}