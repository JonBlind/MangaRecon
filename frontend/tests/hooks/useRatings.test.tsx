import type { ReactNode } from "react";
import { act, renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, test, vi } from "vitest";
import { ratingKeys, useDeleteRating, useSaveRating } from "../../src/hooks/useRatings";

const mocks = vi.hoisted(() => ({
  deleteRating: vi.fn(),
  getRatingForManga: vi.fn(),
  saveRating: vi.fn(),
}));

vi.mock("../../src/api/ratings", () => mocks);

function setup() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  const invalidateQueries = vi.spyOn(queryClient, "invalidateQueries");

  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }

  return { queryClient, invalidateQueries, Wrapper };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("rating mutations", () => {
  test("saving refreshes the personal rating and aggregate consumers", async () => {
    const rating = {
      manga_id: 10,
      personal_rating: 9.5,
      created_at: "2026-08-09T00:00:00Z",
    };
    mocks.saveRating.mockResolvedValueOnce(rating);
    const { queryClient, invalidateQueries, Wrapper } = setup();
    const { result } = renderHook(() => useSaveRating(10), {
      wrapper: Wrapper,
    });

    await act(async () => {
      await result.current.mutateAsync(9.5);
    });

    expect(mocks.saveRating).toHaveBeenCalledWith({
      manga_id: 10,
      personal_rating: 9.5,
    });
    expect(queryClient.getQueryData(ratingKeys.detail(10))).toEqual(rating);
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: ["manga", 10],
    });
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: ["mangas"],
    });
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: ["recommendations", "collection"],
    });
  });

  test("deleting clears the personal rating and refreshes aggregate consumers", async () => {
    mocks.deleteRating.mockResolvedValueOnce(undefined);
    const { queryClient, invalidateQueries, Wrapper } = setup();
    queryClient.setQueryData(ratingKeys.detail(10), {
      manga_id: 10,
      personal_rating: 8.5,
      created_at: "2026-08-09T00:00:00Z",
    });
    const { result } = renderHook(() => useDeleteRating(10), {
      wrapper: Wrapper,
    });

    await act(async () => {
      await result.current.mutateAsync();
    });

    expect(mocks.deleteRating).toHaveBeenCalledWith(10);
    expect(queryClient.getQueryData(ratingKeys.detail(10))).toBeNull();
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: ["manga", 10],
    });
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: ["mangas"],
    });
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: ["recommendations", "collection"],
    });
  });
});
