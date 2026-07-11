import { vi } from "vitest";
import { ApiRequestError } from "../../src/api/http";
import { login, logout, me, register } from "../../src/api/auth";

const mocks = vi.hoisted(() => ({
  apiFetch: vi.fn(),
}));

vi.mock("../../src/api/http", async () => {
  const actual = await vi.importActual<typeof import("../../src/api/http")>(
    "../../src/api/http"
  );

  return {
    ...actual,
    apiFetch: mocks.apiFetch,
  };
});

beforeEach(() => {
  vi.clearAllMocks();
});

describe("auth api", () => {
  test("login posts form-encoded credentials", async () => {
    mocks.apiFetch.mockResolvedValueOnce({ data: undefined });

    await login("test@example.com", "password123");

    expect(mocks.apiFetch).toHaveBeenCalledWith("/auth/jwt/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: expect.any(URLSearchParams),
    });

    const options = mocks.apiFetch.mock.calls[0][1];
    const body = options.body as URLSearchParams;

    expect(body.get("username")).toBe("test@example.com");
    expect(body.get("password")).toBe("password123");
  });

  test("logout posts to logout endpoint", async () => {
    mocks.apiFetch.mockResolvedValueOnce({ data: undefined });

    await logout();

    expect(mocks.apiFetch).toHaveBeenCalledWith("/auth/jwt/logout", {
      method: "POST",
    });
  });

  test("register posts JSON payload", async () => {
    mocks.apiFetch.mockResolvedValueOnce({ data: undefined });

    const payload = {
      email: "test@example.com",
      password: "password123",
      username: "testuser",
      displayname: "Test User",
    };

    await register(payload);

    expect(mocks.apiFetch).toHaveBeenCalledWith("/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  });

  test("me returns current user data", async () => {
    const user = {
      id: "user-1",
      email: "test@example.com",
      username: "testuser",
      displayname: "Test User",
    };

    mocks.apiFetch.mockResolvedValueOnce({ data: user });

    await expect(me()).resolves.toEqual(user);

    expect(mocks.apiFetch).toHaveBeenCalledWith("/profiles/me", {
      method: "GET",
    });
  });

  test("me returns null on 401", async () => {
    mocks.apiFetch.mockRejectedValueOnce(
      new ApiRequestError("Unauthorized", 401, undefined)
    );

    await expect(me()).resolves.toBeNull();
  });

  test("me rethrows non-401 ApiRequestError", async () => {
    const error = new ApiRequestError("Server error", 500, undefined);

    mocks.apiFetch.mockRejectedValueOnce(error);

    await expect(me()).rejects.toBe(error);
  });

  test("me rethrows unknown errors", async () => {
    const error = new Error("Network failed");

    mocks.apiFetch.mockRejectedValueOnce(error);

    await expect(me()).rejects.toBe(error);
  });
});