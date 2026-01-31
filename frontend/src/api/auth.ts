import { apiFetch } from "./http";

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
