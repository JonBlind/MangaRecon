import { beforeEach, describe, expect, test, vi } from "vitest";
import { deleteAccount, updateProfile } from "../../src/api/profile";

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

describe("profiles api", () => {
  test("updates display name", async () => {
    const response = {
      data: {
        id: "user-1",
        email: "test@example.com",
        username: "testuser",
        displayname: "Jonathan",
      },
    };

    mocks.apiFetch.mockResolvedValueOnce(response);

    await expect(
      updateProfile({
        displayname: "Jonathan",
      })
    ).resolves.toEqual(response);

    expect(mocks.apiFetch).toHaveBeenCalledWith(
      "/profiles/me",
      {
        method: "PATCH",
        body: JSON.stringify({
          displayname: "Jonathan",
        }),
      }
    );
  });

  test("supports empty display name", async () => {
    const response = {
      data: {
        id: "user-1",
        displayname: "",
      },
    };

    mocks.apiFetch.mockResolvedValueOnce(response);

    await updateProfile({
      displayname: "",
    });

    expect(mocks.apiFetch).toHaveBeenCalledWith(
      "/profiles/me",
      {
        method: "PATCH",
        body: JSON.stringify({
          displayname: "",
        }),
      }
    );
  });

  test("submits the adult-content preference and age confirmation", async () => {
    const response = {
      data: {
        id: "user-1",
        show_adult_content: true,
      },
    };

    mocks.apiFetch.mockResolvedValueOnce(response);

    await updateProfile({
      show_adult_content: true,
      confirm_adult_content_age: true,
    });

    expect(mocks.apiFetch).toHaveBeenCalledWith(
      "/profiles/me",
      {
        method: "PATCH",
        body: JSON.stringify({
          show_adult_content: true,
          confirm_adult_content_age: true,
        }),
      },
    );
  });

  test("deletes the authenticated account only with password and confirmation", async () => {
    mocks.apiFetch.mockResolvedValueOnce({ status: "success" });

    await deleteAccount("secret-password");

    expect(mocks.apiFetch).toHaveBeenCalledWith("/profiles/me", {
      method: "DELETE",
      body: JSON.stringify({
        current_password: "secret-password",
        confirmation: "DELETE",
      }),
    });
  });
});
