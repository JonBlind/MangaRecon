import { apiFetch } from "./http";
import type { UserMe } from "../types/auth";

export type ProfileUpdatePayload = {
  username?: string;
  displayname?: string;
};

export async function updateProfile(
  payload: ProfileUpdatePayload
) {
  return apiFetch<UserMe>("/profiles/me", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}