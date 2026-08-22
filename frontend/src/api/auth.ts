import { apiFetch, ApiRequestError } from "./http";
import type { UserMe } from "../types/auth";

export async function login(email: string, password: string) {
  const body = new URLSearchParams();
  body.set("username", email);
  body.set("password", password);

  return apiFetch<void>("/auth/jwt/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
}

export async function logout() {
  return apiFetch<void>("/auth/jwt/logout", {
    method: "POST",
  });
}

// Register is JSON
export type RegisterPayload = {
  email: string;
  password: string;
  username: string;
  displayname: string;
};

export async function register(payload: RegisterPayload) {
  return apiFetch<void>("/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function requestVerificationEmail(email: string) {
  return apiFetch<void>("/auth/request-verify-token", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export async function verifyEmail(token: string) {
  return apiFetch<UserMe>("/auth/verify", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
}

export async function requestPasswordReset(email: string) {
  return apiFetch<void>("/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export async function validatePasswordResetToken(token: string) {
  const query = new URLSearchParams({ token });

  return apiFetch<void>(`/auth/reset-password?${query.toString()}`, {
    method: "GET",
  });
}

export async function resetPassword(token: string, password: string) {
  return apiFetch<void>("/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({ token, password }),
  });
}

export async function me(): Promise<UserMe | null> {
  try {
    const res = await apiFetch<UserMe>("/profiles/me", { method: "GET" });
    return res.data;
  } catch (error) {
    if (error instanceof ApiRequestError && error.statusCode === 401) {
      return null;
    }
    throw error;
  }
}
