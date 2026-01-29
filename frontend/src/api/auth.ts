import { apiFetch } from "./http";

export async function login(email: string, password: string) {
  const body = new URLSearchParams();
  body.set("username", email); // FastAPI Users uses "username" even if it's email
  body.set("password", password);

  // login route usually returns 204 or a token body depending on config;
  // but cookie is what matters. We'll just treat success as void.
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
  is_active?: boolean;
  is_superuser?: boolean;
  is_verified?: boolean;
};

export async function register(payload: RegisterPayload) {
  return apiFetch<void>("/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function me() {
  return apiFetch<any>("/users/me", { method: "GET" });
}
