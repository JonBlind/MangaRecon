import { apiFetch } from "./http";
import type { UserMe } from "../types/auth";

export type ProfileUpdatePayload = {
  username?: string;
  displayname?: string;
  show_adult_content?: boolean;
  confirm_adult_content_age?: boolean;
};

export async function updateProfile(
  payload: ProfileUpdatePayload
) {
  return apiFetch<UserMe>("/profiles/me", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}
