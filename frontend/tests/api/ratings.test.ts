import { beforeEach, describe, expect, test, vi } from "vitest";
import { deleteRating, getRatingForManga, saveRating } from "../../src/api/ratings";
import { ApiRequestError } from "../../src/api/http";

const mocks = vi.hoisted(() => ({
  apiFetch: vi.fn(),
}));

vi.mock("../../src/api/http", async () => {
  const actual =
    await vi.importActual<typeof import("../../src/api/http")>("../../src/api/http");
  return {
    ...actual,
    apiFetch: mocks.apiFetch,
  };
});

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ratings api", () => {
  test("gets the current user's rating for a manga", async () => {
    const rating = {
      manga_id: 10,
      personal_rating: 8.5,
      created_at: "2026-08-09T00:00:00Z",
    };
    mocks.apiFetch.mockResolvedValueOnce({ data: rating });

    await expect(getRatingForManga(10)).resolves.toEqual(rating);
    expect(mocks.apiFetch).toHaveBeenCalledWith("/ratings?manga_id=10", {
      method: "GET",
    });
  });

  test("treats a missing personal rating as unrated", async () => {
    mocks.apiFetch.mockRejectedValueOnce(
      new ApiRequestError("Rating not found.", 404, "RATING_NOT_FOUND"),
    );

    await expect(getRatingForManga(10)).resolves.toBeNull();
  });

  test("does not hide unrelated rating fetch failures", async () => {
    const error = new ApiRequestError("Server error", 500);
    mocks.apiFetch.mockRejectedValueOnce(error);

    await expect(getRatingForManga(10)).rejects.toBe(error);
  });

  test("saves a rating with the upsert endpoint", async () => {
    const payload = { manga_id: 10, personal_rating: 9.5 };
    const rating = {
      ...payload,
      created_at: "2026-08-09T00:00:00Z",
    };
    mocks.apiFetch.mockResolvedValueOnce({ data: rating });

    await expect(saveRating(payload)).resolves.toEqual(rating);
    expect(mocks.apiFetch).toHaveBeenCalledWith("/ratings", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  });

  test("deletes a personal rating", async () => {
    mocks.apiFetch.mockResolvedValueOnce({ data: { manga_id: 10 } });

    await expect(deleteRating(10)).resolves.toBeUndefined();
    expect(mocks.apiFetch).toHaveBeenCalledWith("/ratings/10", {
      method: "DELETE",
    });
  });
});
