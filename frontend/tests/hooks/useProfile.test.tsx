import type { ReactNode } from "react";
import { act, renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, test, vi } from "vitest";
import { useUpdateProfile } from "../../src/hooks/useProfile";


const mocks = vi.hoisted(() => ({
  updateProfile: vi.fn(),
}));

vi.mock("../../src/api/profile", () => mocks);

function setup() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    );
  }

  return { queryClient, Wrapper };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("profile mutation cache isolation", () => {
  test("replaces current user and removes visibility-sensitive queries", async () => {
    const updatedUser = {
      id: "user-1",
      email: "test@example.com",
      username: "testuser",
      displayname: "Test User",
      username_changed_at: null,
      show_adult_content: true,
      created_at: "2026-01-01T00:00:00Z",
    };
    mocks.updateProfile.mockResolvedValueOnce({ data: updatedUser });

    const { queryClient, Wrapper } = setup();
    queryClient.setQueryData(["manga", 1], { manga_id: 1 });
    queryClient.setQueryData(["mangas", { page: 1 }], { items: [] });
    queryClient.setQueryData(["genres"], [{ genre_id: 1 }]);
    queryClient.setQueryData(
      ["recommendations", "collection", 3],
      { items: [] },
    );

    const { result } = renderHook(() => useUpdateProfile(), {
      wrapper: Wrapper,
    });

    await act(async () => {
      await result.current.mutateAsync({
        show_adult_content: true,
        confirm_adult_content_age: true,
      });
    });

    expect(queryClient.getQueryData(["me"])).toEqual(updatedUser);
    expect(queryClient.getQueryData(["manga", 1])).toBeUndefined();
    expect(
      queryClient.getQueryData(["mangas", { page: 1 }]),
    ).toBeUndefined();
    expect(queryClient.getQueryData(["genres"])).toBeUndefined();
    expect(
      queryClient.getQueryData(["recommendations", "collection", 3]),
    ).toBeUndefined();
  });

  test("keeps catalog queries for an unrelated profile update", async () => {
    mocks.updateProfile.mockResolvedValueOnce({
      data: {
        id: "user-1",
        displayname: "Updated User",
        show_adult_content: false,
      },
    });

    const { queryClient, Wrapper } = setup();
    queryClient.setQueryData(["manga", 1], { manga_id: 1 });

    const { result } = renderHook(() => useUpdateProfile(), {
      wrapper: Wrapper,
    });

    await act(async () => {
      await result.current.mutateAsync({
        displayname: "Updated User",
      });
    });

    expect(queryClient.getQueryData(["manga", 1])).toEqual({
      manga_id: 1,
    });
  });
});
