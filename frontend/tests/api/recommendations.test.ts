import { beforeEach, describe, expect, test, vi } from "vitest";
import {
  getRecommendationsForCollection,
  getRecommendationsForQueryList,
} from "../../src/api/recommendations";

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

describe("recommendations api", () => {
  test("gets collection recommendations with default parameters", async () => {
    const response = {
      total_results: 0,
      page: 1,
      size: 20,
      items: [],
    };

    mocks.apiFetch.mockResolvedValueOnce({
      data: response,
    });

    await expect(
      getRecommendationsForCollection(5)
    ).resolves.toEqual(response);

    expect(mocks.apiFetch).toHaveBeenCalledWith(
      "/recommendations/5?page=1&size=20&order_by=score&order_dir=desc",
      {
        method: "GET",
      }
    );
  });

  test("gets collection recommendations with custom parameters", async () => {
    const response = {
      total_results: 3,
      page: 2,
      size: 10,
      items: [],
    };

    mocks.apiFetch.mockResolvedValueOnce({
      data: response,
    });

    await expect(
      getRecommendationsForCollection(10, {
        page: 2,
        size: 10,
        order_by: "external_average_rating",
        order_dir: "asc",
      })
    ).resolves.toEqual(response);

    expect(mocks.apiFetch).toHaveBeenCalledWith(
      "/recommendations/10?page=2&size=10&order_by=external_average_rating&order_dir=asc",
      {
        method: "GET",
      }
    );
  });

  test("gets recommendations for query list with defaults", async () => {
    const payload = {
      manga_ids: [1, 2, 3],
    };

    const response = {
      total_results: 5,
      page: 1,
      size: 20,
      items: [],
    };

    mocks.apiFetch.mockResolvedValueOnce({
      data: response,
    });

    await expect(
      getRecommendationsForQueryList(payload)
    ).resolves.toEqual(response);

    expect(mocks.apiFetch).toHaveBeenCalledWith(
      "/recommendations/query-list?page=1&size=20&order_by=score&order_dir=desc",
      {
        method: "POST",
        body: JSON.stringify(payload),
      }
    );
  });

  test("gets recommendations for query list with custom parameters", async () => {
    const payload = {
      manga_ids: [10, 20],
    };

    const response = {
      total_results: 2,
      page: 3,
      size: 5,
      items: [],
    };

    mocks.apiFetch.mockResolvedValueOnce({
      data: response,
    });

    await expect(
      getRecommendationsForQueryList(payload, {
        page: 3,
        size: 5,
        order_by: "title",
        order_dir: "asc",
      })
    ).resolves.toEqual(response);

    expect(mocks.apiFetch).toHaveBeenCalledWith(
      "/recommendations/query-list?page=3&size=5&order_by=title&order_dir=asc",
      {
        method: "POST",
        body: JSON.stringify(payload),
      }
    );
  });

  test("supports empty manga id list", async () => {
    const payload = {
      manga_ids: [],
    };

    const response = {
      total_results: 0,
      page: 1,
      size: 20,
      items: [],
    };

    mocks.apiFetch.mockResolvedValueOnce({
      data: response,
    });

    await getRecommendationsForQueryList(payload);

    expect(mocks.apiFetch).toHaveBeenCalledWith(
      "/recommendations/query-list?page=1&size=20&order_by=score&order_dir=desc",
      {
        method: "POST",
        body: JSON.stringify(payload),
      }
    );
  });
});