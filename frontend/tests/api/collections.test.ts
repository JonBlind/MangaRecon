import { beforeEach, describe, expect, test, vi } from "vitest";
import {
  addMangaToCollection,
  addMangasBulkToCollection,
  createCollection,
  deleteCollection,
  getCollectionById,
  listCollections,
  listMangaInCollection,
  removeMangaFromCollection,
  updateCollection,
} from "../../src/api/collections";

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

describe("collections api", () => {
  test("listCollections uses default pagination", async () => {
    const page = { items: [], total_results: 0, page: 1, size: 20 };

    mocks.apiFetch.mockResolvedValueOnce({ data: page });

    await expect(listCollections()).resolves.toEqual(page);

    expect(mocks.apiFetch).toHaveBeenCalledWith(
      "/collections?page=1&size=20&order=desc",
      { method: "GET" }
    );
  });

  test("listCollections uses provided pagination", async () => {
    const page = { items: [], total_results: 0, page: 2, size: 50 };

    mocks.apiFetch.mockResolvedValueOnce({ data: page });

    await listCollections({
      page: 2,
      size: 50,
      order: "asc",
    });

    expect(mocks.apiFetch).toHaveBeenCalledWith(
      "/collections?page=2&size=50&order=asc",
      { method: "GET" }
    );
  });

  test("getCollectionById returns collection", async () => {
    const collection = {
      collection_id: 1,
      collection_name: "Favorites",
    };

    mocks.apiFetch.mockResolvedValueOnce({ data: collection });

    await expect(getCollectionById(1)).resolves.toEqual(collection);

    expect(mocks.apiFetch).toHaveBeenCalledWith("/collections/1", {
      method: "GET",
    });
  });

  test("createCollection posts payload", async () => {
    const payload = {
      collection_name: "Favorites",
      description: "Best manga",
    };

    mocks.apiFetch.mockResolvedValueOnce({ data: payload });

    await createCollection(payload);

    expect(mocks.apiFetch).toHaveBeenCalledWith("/collections", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  });

  test("updateCollection puts payload", async () => {
    const payload = {
      collection_name: "Updated",
      description: "Updated description",
    };

    mocks.apiFetch.mockResolvedValueOnce({ data: payload });

    await updateCollection(5, payload);

    expect(mocks.apiFetch).toHaveBeenCalledWith("/collections/5", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  });

  test("deleteCollection sends delete request", async () => {
    mocks.apiFetch.mockResolvedValueOnce({ data: undefined });

    await deleteCollection(3);

    expect(mocks.apiFetch).toHaveBeenCalledWith("/collections/3", {
      method: "DELETE",
    });
  });

  test("listMangaInCollection uses default pagination", async () => {
    const page = { items: [], total_results: 0, page: 1, size: 20 };

    mocks.apiFetch.mockResolvedValueOnce({ data: page });

    await listMangaInCollection(10);

    expect(mocks.apiFetch).toHaveBeenCalledWith(
      "/collections/10/mangas?page=1&size=20&order=desc",
      {
        method: "GET",
      }
    );
  });

  test("listMangaInCollection uses supplied pagination", async () => {
    const page = { items: [], total_results: 0, page: 4, size: 100 };

    mocks.apiFetch.mockResolvedValueOnce({ data: page });

    await listMangaInCollection(10, {
      page: 4,
      size: 100,
      order: "asc",
    });

    expect(mocks.apiFetch).toHaveBeenCalledWith(
      "/collections/10/mangas?page=4&size=100&order=asc",
      {
        method: "GET",
      }
    );
  });

  test("addMangaToCollection posts manga id", async () => {
    mocks.apiFetch.mockResolvedValueOnce({ data: undefined });

    await addMangaToCollection(5, 99);

    expect(mocks.apiFetch).toHaveBeenCalledWith(
      "/collections/5/mangas",
      {
        method: "POST",
        body: JSON.stringify({
          manga_id: 99,
        }),
      }
    );
  });

  test("addMangasBulkToCollection posts manga ids", async () => {
    const response = {
      added_count: 2,
      failed_count: 0,
      added_ids: [1, 2],
      failed: [],
    };

    mocks.apiFetch.mockResolvedValueOnce({
      data: response,
    });

    await expect(
      addMangasBulkToCollection(5, [1, 2])
    ).resolves.toEqual(response);

    expect(mocks.apiFetch).toHaveBeenCalledWith(
      "/collections/5/mangas/bulk",
      {
        method: "POST",
        body: JSON.stringify({
          manga_ids: [1, 2],
        }),
      }
    );
  });

  test("removeMangaFromCollection deletes manga id", async () => {
    mocks.apiFetch.mockResolvedValueOnce({ data: undefined });

    await removeMangaFromCollection(7, 42);

    expect(mocks.apiFetch).toHaveBeenCalledWith(
      "/collections/7/mangas",
      {
        method: "DELETE",
        body: JSON.stringify({
          manga_id: 42,
        }),
      }
    );
  });
});