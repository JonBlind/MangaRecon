import { beforeEach, describe, expect, test, vi } from "vitest";
import { getMangaById, searchMangas } from "../../src/api/manga";

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

describe("manga api", () => {
  test("getMangaById requests manga by id", async () => {
    const manga = {
      manga_id: 42,
      title: "Naruto",
    };

    mocks.apiFetch.mockResolvedValueOnce({
      data: manga,
    });

    await expect(getMangaById(42)).resolves.toEqual(manga);

    expect(mocks.apiFetch).toHaveBeenCalledWith("/mangas/42");
  });

  test("searchMangas uses default pagination", async () => {
    const response = {
      total_results: 0,
      page: 1,
      size: 50,
      items: [],
    };

    mocks.apiFetch.mockResolvedValueOnce({
      data: response,
    });

    await expect(searchMangas({})).resolves.toEqual(response);

    expect(mocks.apiFetch).toHaveBeenCalledWith("/mangas/?page=1&size=50");
  });

  test("searchMangas trims title", async () => {
    mocks.apiFetch.mockResolvedValueOnce({
      data: {
        total_results: 0,
        page: 1,
        size: 50,
        items: [],
      },
    });

    await searchMangas({
      title: "   Naruto   ",
    });

    expect(mocks.apiFetch).toHaveBeenCalledWith("/mangas/?title=Naruto&page=1&size=50");
  });

  test("searchMangas ignores blank title", async () => {
    mocks.apiFetch.mockResolvedValueOnce({
      data: {
        total_results: 0,
        page: 1,
        size: 50,
        items: [],
      },
    });

    await searchMangas({
      title: "      ",
    });

    expect(mocks.apiFetch).toHaveBeenCalledWith("/mangas/?page=1&size=50");
  });

  test("searchMangas uses supplied pagination", async () => {
    mocks.apiFetch.mockResolvedValueOnce({
      data: {
        total_results: 0,
        page: 3,
        size: 10,
        items: [],
      },
    });

    await searchMangas({
      page: 3,
      size: 10,
    });

    expect(mocks.apiFetch).toHaveBeenCalledWith("/mangas/?page=3&size=10");
  });

  test("searchMangas includes ordering", async () => {
    mocks.apiFetch.mockResolvedValueOnce({
      data: {
        total_results: 0,
        page: 1,
        size: 50,
        items: [],
      },
    });

    await searchMangas({
      order_by: "title",
      order_dir: "asc",
    });

    expect(mocks.apiFetch).toHaveBeenCalledWith(
      "/mangas/?page=1&size=50&order_by=title&order_dir=asc",
    );
  });

  test("searchMangas includes repeated genre filters", async () => {
    mocks.apiFetch.mockResolvedValueOnce({
      data: {
        total_results: 0,
        page: 1,
        size: 50,
        items: [],
      },
    });

    await searchMangas({
      genre_ids: [5, 7],
    });

    expect(mocks.apiFetch).toHaveBeenCalledWith(
      "/mangas/?page=1&size=50&genre_ids=5&genre_ids=7",
    );
  });

  test("searchMangas includes repeated tag filters", async () => {
    mocks.apiFetch.mockResolvedValueOnce({
      data: {
        total_results: 0,
        page: 1,
        size: 50,
        items: [],
      },
    });

    await searchMangas({
      tag_ids: [8, 9],
    });

    expect(mocks.apiFetch).toHaveBeenCalledWith(
      "/mangas/?page=1&size=50&tag_ids=8&tag_ids=9",
    );
  });

  test("searchMangas includes repeated demographic filters", async () => {
    mocks.apiFetch.mockResolvedValueOnce({
      data: {
        total_results: 0,
        page: 1,
        size: 50,
        items: [],
      },
    });

    await searchMangas({
      demo_ids: [2, 3],
    });

    expect(mocks.apiFetch).toHaveBeenCalledWith(
      "/mangas/?page=1&size=50&demo_ids=2&demo_ids=3",
    );
  });

  test("searchMangas includes repeated metadata exclusions", async () => {
    mocks.apiFetch.mockResolvedValueOnce({
      data: {
        total_results: 0,
        page: 1,
        size: 50,
        items: [],
      },
    });

    await searchMangas({
      exclude_genres: [5, 7],
      exclude_tags: [8, 9],
      exclude_demos: [2, 3],
    });

    expect(mocks.apiFetch).toHaveBeenCalledWith(
      "/mangas/?page=1&size=50&exclude_genres=5&exclude_genres=7&exclude_tags=8&exclude_tags=9&exclude_demos=2&exclude_demos=3",
    );
  });

  test("searchMangas includes every filter together", async () => {
    const response = {
      total_results: 2,
      page: 2,
      size: 25,
      items: [
        {
          manga_id: 1,
          title: "Naruto",
        },
        {
          manga_id: 2,
          title: "Bleach",
        },
      ],
    };

    mocks.apiFetch.mockResolvedValueOnce({
      data: response,
    });

    await expect(
      searchMangas({
        title: " Naruto ",
        page: 2,
        size: 25,
        order_by: "external_average_rating",
        order_dir: "desc",
        genre_ids: [1, 4],
        exclude_genres: [9],
        tag_ids: [2],
        exclude_tags: [8],
        demo_ids: [3],
        exclude_demos: [7],
        match_mode: "or",
      }),
    ).resolves.toEqual(response);

    expect(mocks.apiFetch).toHaveBeenCalledWith(
      "/mangas/?title=Naruto&page=2&size=25&order_by=external_average_rating&order_dir=desc&genre_ids=1&genre_ids=4&exclude_genres=9&tag_ids=2&exclude_tags=8&demo_ids=3&exclude_demos=7&match_mode=or",
    );
  });

  test("searchMangas ignores empty metadata selections", async () => {
    mocks.apiFetch.mockResolvedValueOnce({
      data: {
        total_results: 0,
        page: 1,
        size: 50,
        items: [],
      },
    });

    await searchMangas({
      genre_ids: [],
      exclude_genres: [],
      tag_ids: [],
      exclude_tags: [],
      demo_ids: [],
      exclude_demos: [],
    });

    expect(mocks.apiFetch).toHaveBeenCalledWith("/mangas/?page=1&size=50");
  });

  test("searchMangas forwards an abort signal", async () => {
    mocks.apiFetch.mockResolvedValueOnce({
      data: {
        total_results: 0,
        page: 1,
        size: 50,
        items: [],
      },
    });

    const controller = new AbortController();

    await searchMangas({ title: "Naruto" }, controller.signal);

    expect(mocks.apiFetch).toHaveBeenCalledWith("/mangas/?title=Naruto&page=1&size=50", {
      signal: controller.signal,
    });
  });
});
