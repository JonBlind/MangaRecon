import type { ReactNode } from "react";
import { act, renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, test, vi } from "vitest";
import {
  useAddMangaToCollection,
  useDeleteCollection,
  useRemoveMangaFromCollection,
} from "../../src/hooks/useCollections";

const mocks = vi.hoisted(() => ({
  addMangaToCollection: vi.fn(),
  createCollection: vi.fn(),
  deleteCollection: vi.fn(),
  getCollectionById: vi.fn(),
  listCollections: vi.fn(),
  listMangaInCollection: vi.fn(),
  removeMangaFromCollection: vi.fn(),
  updateCollection: vi.fn(),
}));

vi.mock("../../src/api/collections", () => mocks);

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
  mocks.addMangaToCollection.mockResolvedValue(undefined);
  mocks.deleteCollection.mockResolvedValue(undefined);
  mocks.removeMangaFromCollection.mockResolvedValue(undefined);
});

describe("collection mutation recommendation cache invalidation", () => {
  test("adding manga invalidates every collection recommendation query", async () => {
    const { invalidateQueries, Wrapper } = setup();
    const { result } = renderHook(() => useAddMangaToCollection(5), {
      wrapper: Wrapper,
    });

    await act(async () => {
      await result.current.mutateAsync(42);
    });

    expect(mocks.addMangaToCollection).toHaveBeenCalledWith(5, 42);
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: ["recommendations", "collection"],
    });
  });

  test("removing manga invalidates every collection recommendation query", async () => {
    const { invalidateQueries, Wrapper } = setup();
    const { result } = renderHook(() => useRemoveMangaFromCollection(5), {
      wrapper: Wrapper,
    });

    await act(async () => {
      await result.current.mutateAsync(42);
    });

    expect(mocks.removeMangaFromCollection).toHaveBeenCalledWith(5, 42);
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: ["recommendations", "collection"],
    });
  });

  test("deleting a collection invalidates every collection recommendation query", async () => {
    const { invalidateQueries, Wrapper } = setup();
    const { result } = renderHook(() => useDeleteCollection(), {
      wrapper: Wrapper,
    });

    await act(async () => {
      await result.current.mutateAsync(5);
    });

    expect(mocks.deleteCollection).toHaveBeenCalledWith(5);
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: ["recommendations", "collection"],
    });
  });
});
