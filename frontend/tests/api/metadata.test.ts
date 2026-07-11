import { beforeEach, describe, expect, test, vi } from "vitest";
import {
  getDemographics,
  getGenres,
  getTags,
} from "../../src/api/metadata";

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

describe("metadata api", () => {
  test("getGenres returns genre list", async () => {
    const genres = [
      { genre_id: 1, genre_name: "Action" },
      { genre_id: 2, genre_name: "Adventure" },
    ];

    mocks.apiFetch.mockResolvedValueOnce({
      data: {
        items: genres,
      },
    });

    await expect(getGenres()).resolves.toEqual(genres);

    expect(mocks.apiFetch).toHaveBeenCalledWith(
      "/metadata/genres"
    );
  });

  test("getTags returns tag list", async () => {
    const tags = [
      { tag_id: 1, tag_name: "Shounen" },
      { tag_id: 2, tag_name: "Magic" },
    ];

    mocks.apiFetch.mockResolvedValueOnce({
      data: {
        items: tags,
      },
    });

    await expect(getTags()).resolves.toEqual(tags);

    expect(mocks.apiFetch).toHaveBeenCalledWith(
      "/metadata/tags"
    );
  });

  test("getDemographics returns demographic list", async () => {
    const demographics = [
      {
        demographic_id: 1,
        demographic_name: "Seinen",
      },
    ];

    mocks.apiFetch.mockResolvedValueOnce({
      data: {
        items: demographics,
      },
    });

    await expect(getDemographics()).resolves.toEqual(demographics);

    expect(mocks.apiFetch).toHaveBeenCalledWith(
      "/metadata/demographics"
    );
  });
});