import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import Search from "../../src/pages/Search";
import { renderWithProviders } from "../testUtils";

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),

  searchMangas: vi.fn(),
  getGenres: vi.fn(),
  getTags: vi.fn(),
  getDemographics: vi.fn(),
  addMangasBulkToCollection: vi.fn(),

  toggleSelection: vi.fn(),
  clearSelection: vi.fn(),
  removeSelectedIds: vi.fn(),

  user: null as unknown,
  selectedIds: [] as number[],
  selectedCount: 0,
}));

vi.mock("react-router-dom", async () => {
  const actual =
    await vi.importActual<typeof import("react-router-dom")>("react-router-dom");

  return {
    ...actual,
    useNavigate: () => mocks.navigate,
  };
});

vi.mock("../../src/api/manga", () => ({
  searchMangas: mocks.searchMangas,
}));

vi.mock("../../src/api/metadata", () => ({
  getGenres: mocks.getGenres,
  getTags: mocks.getTags,
  getDemographics: mocks.getDemographics,
}));

vi.mock("../../src/api/collections", () => ({
  addMangasBulkToCollection: mocks.addMangasBulkToCollection,
}));

vi.mock("../../src/hooks/useMe", () => ({
  useMe: () => ({
    data: mocks.user,
    isLoading: false,
  }),
}));

vi.mock("../../src/hooks/useMangaSelection", () => ({
  useMangaSelection: () => ({
    selectedIds: mocks.selectedIds,
    selectedCount: mocks.selectedCount,
    toggleSelection: mocks.toggleSelection,
    clearSelection: mocks.clearSelection,
    removeSelectedIds: mocks.removeSelectedIds,
    isSelected: (mangaId: number) => mocks.selectedIds.includes(mangaId),
  }),
}));

vi.mock("../../src/hooks/useCollections", () => ({
  useCollections: () => ({
    data: {
      total_results: 1,
      page: 1,
      size: 100,
      items: [
        {
          collection_id: 1,
          collection_name: "Favorites",
          description: "Favorite manga",
          created_at: "2026-01-01T00:00:00Z",
        },
      ],
    },
    isLoading: false,
    isError: false,
  }),
  useCreateCollection: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
}));

const mangaResults = {
  total_results: 2,
  page: 1,
  size: 25,
  items: [
    {
      manga_id: 10,
      title: "Naruto",
      cover_image_url: null,
      external_average_rating: 4.5,
      genres: [],
    },
    {
      manga_id: 20,
      title: "One Piece",
      cover_image_url: null,
      external_average_rating: 4.8,
      genres: [],
    },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  sessionStorage.clear();

  mocks.user = null;
  mocks.selectedIds = [];
  mocks.selectedCount = 0;

  mocks.getGenres.mockResolvedValue([{ genre_id: 1, genre_name: "Action" }]);
  mocks.getTags.mockResolvedValue([{ tag_id: 1, tag_name: "Adventure" }]);
  mocks.getDemographics.mockResolvedValue([
    { demographic_id: 1, demographic_name: "Shounen" },
  ]);

  mocks.searchMangas.mockResolvedValue(mangaResults);
});

describe("Search Page", () => {
  test("renders search page and filters", async () => {
    renderWithProviders(<Search />);

    expect(screen.getByRole("heading", { name: /^search$/i })).toBeInTheDocument();

    expect(screen.getByPlaceholderText(/e\.g\. naruto/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText(/2 results/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/action/i)).toBeInTheDocument();
    expect(screen.getByText(/adventure/i)).toBeInTheDocument();
    expect(screen.getByText(/shounen/i)).toBeInTheDocument();
  });

  test("renders manga results", async () => {
    renderWithProviders(<Search />);

    expect(await screen.findByText(/naruto/i)).toBeInTheDocument();
    expect(await screen.findByText(/one piece/i)).toBeInTheDocument();
  });

  test("shows loading results state", () => {
    mocks.searchMangas.mockReturnValue(new Promise(() => {}));

    renderWithProviders(<Search />);

    expect(screen.getByText(/loading results/i)).toBeInTheDocument();
  });

  test("debounces title searches until typing pauses for 450 ms", async () => {
    renderWithProviders(<Search />);

    await waitFor(() => {
      expect(mocks.searchMangas).toHaveBeenCalledTimes(1);
    });

    vi.useFakeTimers();

    const titleInput = screen.getByPlaceholderText(/e\.g\. naruto/i);

    fireEvent.change(titleInput, {
      target: { value: "B" },
    });
    fireEvent.change(titleInput, {
      target: { value: "Bl" },
    });
    fireEvent.change(titleInput, {
      target: { value: "Bleach" },
    });

    expect(mocks.searchMangas).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(449);
    });

    expect(mocks.searchMangas).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });

    expect(mocks.searchMangas).toHaveBeenCalledTimes(2);
    expect(mocks.searchMangas).toHaveBeenLastCalledWith(
      expect.objectContaining({
        title: "Bleach",
        page: 1,
        size: 25,
        order_by: "title",
        order_dir: "asc",
      }),
      expect.anything(),
    );

    vi.useRealTimers();
  });

  test("searches immediately when Enter is pressed", async () => {
    renderWithProviders(<Search />);

    await waitFor(() => {
      expect(mocks.searchMangas).toHaveBeenCalledTimes(1);
    });

    const titleInput = screen.getByPlaceholderText(/e\.g\. naruto/i);

    fireEvent.change(titleInput, {
      target: { value: "Monster" },
    });
    fireEvent.keyDown(titleInput, { key: "Enter", code: "Enter" });

    await waitFor(() => {
      expect(mocks.searchMangas).toHaveBeenLastCalledWith(
        expect.objectContaining({
          title: "Monster",
          page: 1,
        }),
        expect.anything(),
      );
    });
  });

  test("clears an active title search immediately", async () => {
    mocks.searchMangas.mockImplementation((params) => {
      if (params.title === "Monster") {
        return Promise.resolve({
          total_results: 1,
          page: 1,
          size: 25,
          items: [
            {
              manga_id: 30,
              title: "Monster",
              cover_image_url: null,
              external_average_rating: 4.7,
              genres: [],
            },
          ],
        });
      }

      return Promise.resolve(mangaResults);
    });

    renderWithProviders(<Search />);

    await waitFor(() => {
      expect(mocks.searchMangas).toHaveBeenCalledTimes(1);
    });

    const titleInput = screen.getByPlaceholderText(/e\.g\. naruto/i);

    fireEvent.change(titleInput, {
      target: { value: "Monster" },
    });
    fireEvent.keyDown(titleInput, { key: "Enter", code: "Enter" });

    await waitFor(() => {
      expect(mocks.searchMangas).toHaveBeenCalledTimes(2);
    });

    expect(await screen.findByText(/^monster$/i)).toBeInTheDocument();
    expect(screen.queryByText(/^naruto$/i)).not.toBeInTheDocument();

    fireEvent.change(titleInput, {
      target: { value: "" },
    });

    expect(titleInput).toHaveValue("");
    expect(await screen.findByText(/^naruto$/i)).toBeInTheDocument();

    // The blank search is still fresh, so React Query restores it immediately
    // without sending a redundant third request.
    expect(mocks.searchMangas).toHaveBeenCalledTimes(2);
  });

  test("passes React Query's abort signal to manga searches", async () => {
    renderWithProviders(<Search />);

    await waitFor(() => {
      expect(mocks.searchMangas).toHaveBeenCalled();
    });

    expect(mocks.searchMangas.mock.calls[0][1]).toBeInstanceOf(AbortSignal);
  });

  test("selects a manga result", async () => {
    renderWithProviders(<Search />);

    fireEvent.click(await screen.findByRole("button", { name: /select naruto/i }));

    expect(mocks.toggleSelection).toHaveBeenCalledWith(
      expect.objectContaining({
        manga_id: 10,
        title: "Naruto",
      }),
    );
  });

  test("opens auth modal when unauthenticated user tries to save selected manga", async () => {
    mocks.selectedIds = [10];
    mocks.selectedCount = 1;

    renderWithProviders(<Search />);

    fireEvent.click(screen.getByRole("button", { name: /sign in to save/i }));

    expect(await screen.findByText(/sign in required/i)).toBeInTheDocument();
    expect(
      screen.getByText(/you need an account to save manga to a collection/i),
    ).toBeInTheDocument();
  });

  test("navigates to recommendations with selected manga ids", () => {
    mocks.selectedIds = [10, 20];
    mocks.selectedCount = 2;

    renderWithProviders(<Search />);

    fireEvent.click(screen.getByRole("button", { name: /get recommendations/i }));

    expect(sessionStorage.getItem("recommendationSeedIds")).toBe("[10,20]");

    expect(mocks.navigate).toHaveBeenCalledWith("/recommendations", {
      state: {
        mangaIds: [10, 20],
      },
    });
  });

  test("adds selected manga to an existing collection", async () => {
    mocks.user = { id: "user-1", email: "test@example.com" };
    mocks.selectedIds = [10, 20];
    mocks.selectedCount = 2;

    mocks.addMangasBulkToCollection.mockResolvedValueOnce({
      collection_id: 1,
      added_count: 2,
      failed_count: 0,
      added_ids: [10, 20],
      failed: [],
    });

    const { queryClient } = renderWithProviders(<Search />);
    const invalidateQueries = vi.spyOn(queryClient, "invalidateQueries");

    fireEvent.click(screen.getByRole("button", { name: /add to collection/i }));

    expect(
      await screen.findByRole("heading", { name: /add to collection/i }),
    ).toBeInTheDocument();

    fireEvent.change(screen.getByDisplayValue("Select a collection"), {
      target: { value: "1" },
    });

    fireEvent.click(screen.getByRole("button", { name: /^add$/i }));

    await waitFor(() => {
      expect(mocks.addMangasBulkToCollection).toHaveBeenCalledWith(1, [10, 20]);
    });

    await waitFor(() => {
      expect(mocks.removeSelectedIds).toHaveBeenCalledWith([10, 20]);
    });

    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: ["recommendations", "collection"],
    });

    expect(await screen.findByText(/2 manga added to collection/i)).toBeInTheDocument();
  });

  test("clears the current manga selection", () => {
    mocks.selectedIds = [10, 20];
    mocks.selectedCount = 2;

    renderWithProviders(<Search />);

    fireEvent.click(screen.getByRole("button", { name: /clear/i }));

    expect(mocks.clearSelection).toHaveBeenCalledTimes(1);
  });

  test("still navigates to recommendations when session storage fails", () => {
    mocks.selectedIds = [10, 20];
    mocks.selectedCount = 2;

    const setItemSpy = vi
      .spyOn(Storage.prototype, "setItem")
      .mockImplementationOnce(() => {
        throw new Error("Storage unavailable");
      });

    renderWithProviders(<Search />);

    fireEvent.click(screen.getByRole("button", { name: /get recommendations/i }));

    expect(mocks.navigate).toHaveBeenCalledWith("/recommendations", {
      state: {
        mangaIds: [10, 20],
      },
    });

    setItemSpy.mockRestore();
  });

  test("closes auth-required modal", async () => {
    mocks.selectedIds = [10];
    mocks.selectedCount = 1;

    renderWithProviders(<Search />);

    fireEvent.click(screen.getByRole("button", { name: /sign in to save/i }));

    expect(
      await screen.findByRole("heading", { name: /sign in required/i }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /^close$/i }));

    expect(
      screen.queryByRole("heading", { name: /sign in required/i }),
    ).not.toBeInTheDocument();
  });

  test("closes collection modal without adding manga", async () => {
    mocks.user = {
      id: "user-1",
      email: "test@example.com",
    };

    mocks.selectedIds = [10];
    mocks.selectedCount = 1;

    renderWithProviders(<Search />);

    fireEvent.click(screen.getByRole("button", { name: /add to collection/i }));

    expect(
      await screen.findByRole("heading", { name: /add to collection/i }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));

    expect(
      screen.queryByRole("heading", { name: /add to collection/i }),
    ).not.toBeInTheDocument();

    expect(mocks.addMangasBulkToCollection).not.toHaveBeenCalled();
  });

  test("updates genre filter", async () => {
    renderWithProviders(<Search />);

    await screen.findByText(/action/i);

    const selects = screen.getAllByRole("combobox");

    fireEvent.change(selects[0], {
      target: { value: "1" },
    });

    await waitFor(() => {
      expect(mocks.searchMangas).toHaveBeenCalledWith(
        expect.objectContaining({
          genre_id: 1,
          page: 1,
        }),
        expect.anything(),
      );
    });
  });

  test("updates tag filter", async () => {
    renderWithProviders(<Search />);

    await screen.findByText(/adventure/i);

    const selects = screen.getAllByRole("combobox");

    fireEvent.change(selects[1], {
      target: { value: "1" },
    });

    await waitFor(() => {
      expect(mocks.searchMangas).toHaveBeenCalledWith(
        expect.objectContaining({
          tag_id: 1,
          page: 1,
        }),
        expect.anything(),
      );
    });
  });

  test("updates demographic filter", async () => {
    renderWithProviders(<Search />);

    await screen.findByText(/shounen/i);

    const selects = screen.getAllByRole("combobox");

    fireEvent.change(selects[2], {
      target: { value: "1" },
    });

    await waitFor(() => {
      expect(mocks.searchMangas).toHaveBeenCalledWith(
        expect.objectContaining({
          demo_id: 1,
          page: 1,
        }),
        expect.anything(),
      );
    });
  });

  test("clears a selected genre filter", async () => {
    renderWithProviders(<Search />);

    await screen.findByText(/action/i);

    const genreSelect = screen.getAllByRole("combobox")[0];

    fireEvent.change(genreSelect, {
      target: { value: "1" },
    });

    await waitFor(() => {
      expect(mocks.searchMangas).toHaveBeenCalledWith(
        expect.objectContaining({
          genre_id: 1,
        }),
        expect.anything(),
      );
    });

    fireEvent.change(genreSelect, {
      target: { value: "" },
    });

    await waitFor(() => {
      expect(genreSelect).toHaveValue("");
    });

    // Clearing restores the still-fresh unfiltered query from the cache.
    expect(mocks.searchMangas).toHaveBeenCalledTimes(2);
  });

  test("shows metadata loading state", () => {
    mocks.getGenres.mockReturnValue(new Promise(() => {}));
    mocks.getTags.mockReturnValue(new Promise(() => {}));
    mocks.getDemographics.mockReturnValue(new Promise(() => {}));

    renderWithProviders(<Search />);

    expect(screen.getByText(/loading filters/i)).toBeInTheDocument();
  });

  test("shows manga search error message", async () => {
    mocks.searchMangas.mockRejectedValueOnce(new Error("Search request failed"));

    renderWithProviders(<Search />);

    expect(await screen.findByText(/search request failed/i)).toBeInTheDocument();
  });

  test("shows empty results state", async () => {
    mocks.searchMangas.mockResolvedValueOnce({
      total_results: 0,
      page: 1,
      size: 25,
      items: [],
    });

    renderWithProviders(<Search />);

    expect(await screen.findByText(/no results/i)).toBeInTheDocument();
    expect(screen.getByText(/0 results/i)).toBeInTheDocument();
  });

  test("moves to the next and previous results pages", async () => {
    mocks.searchMangas.mockResolvedValue({
      total_results: 60,
      page: 1,
      size: 25,
      items: mangaResults.items,
    });

    renderWithProviders(<Search />);

    await screen.findByText(/60 results/i);

    fireEvent.click(screen.getByRole("button", { name: /next/i }));

    await waitFor(() => {
      expect(mocks.searchMangas).toHaveBeenCalledWith(
        expect.objectContaining({
          page: 2,
        }),
        expect.anything(),
      );
    });

    fireEvent.click(screen.getByRole("button", { name: /prev/i }));

    await waitFor(() => {
      expect(screen.getByText(/page 1 \/ 3/i)).toBeInTheDocument();
    });

    // Page 1 remains fresh in the cache, so going back does not refetch it.
    expect(mocks.searchMangas).toHaveBeenCalledTimes(2);
  });

  test("disables pagination while results are loading", () => {
    mocks.searchMangas.mockReturnValue(new Promise(() => {}));

    renderWithProviders(<Search />);

    expect(screen.getByRole("button", { name: /prev/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /next/i })).toBeDisabled();
  });

  test("shows partial bulk-add feedback", async () => {
    mocks.user = {
      id: "user-1",
      email: "test@example.com",
    };

    mocks.selectedIds = [10, 20];
    mocks.selectedCount = 2;

    mocks.addMangasBulkToCollection.mockResolvedValueOnce({
      collection_id: 1,
      added_count: 1,
      failed_count: 1,
      added_ids: [10],
      failed: [
        {
          manga_id: 20,
          reason: "ALREADY_EXISTS",
        },
      ],
    });

    renderWithProviders(<Search />);

    fireEvent.click(screen.getByRole("button", { name: /add to collection/i }));

    fireEvent.change(await screen.findByDisplayValue("Select a collection"), {
      target: { value: "1" },
    });

    fireEvent.click(screen.getByRole("button", { name: /^add$/i }));

    expect(
      await screen.findByText(/1 manga added, 1 failed\. 1 already in the collection/i),
    ).toBeInTheDocument();

    expect(mocks.removeSelectedIds).toHaveBeenCalledWith([10]);
  });

  test("shows collection-not-found bulk-add feedback", async () => {
    mocks.user = {
      id: "user-1",
      email: "test@example.com",
    };

    mocks.selectedIds = [10];
    mocks.selectedCount = 1;

    mocks.addMangasBulkToCollection.mockResolvedValueOnce({
      collection_id: 1,
      added_count: 0,
      failed_count: 1,
      added_ids: [],
      failed: [
        {
          manga_id: 10,
          reason: "COLLECTION_NOT_FOUND",
        },
      ],
    });

    renderWithProviders(<Search />);

    fireEvent.click(screen.getByRole("button", { name: /add to collection/i }));

    fireEvent.change(await screen.findByDisplayValue("Select a collection"), {
      target: { value: "1" },
    });

    fireEvent.click(screen.getByRole("button", { name: /^add$/i }));

    expect(
      await screen.findByText(
        /no manga were added\. 1 failed because the collection was not found/i,
      ),
    ).toBeInTheDocument();

    expect(mocks.removeSelectedIds).not.toHaveBeenCalled();
  });

  test("shows unknown bulk-add failure feedback", async () => {
    mocks.user = {
      id: "user-1",
      email: "test@example.com",
    };

    mocks.selectedIds = [10];
    mocks.selectedCount = 1;

    mocks.addMangasBulkToCollection.mockResolvedValueOnce({
      collection_id: 1,
      added_count: 0,
      failed_count: 1,
      added_ids: [],
      failed: [
        {
          manga_id: 10,
          reason: "UNKNOWN",
        },
      ],
    });

    renderWithProviders(<Search />);

    fireEvent.click(screen.getByRole("button", { name: /add to collection/i }));

    fireEvent.change(await screen.findByDisplayValue("Select a collection"), {
      target: { value: "1" },
    });

    fireEvent.click(screen.getByRole("button", { name: /^add$/i }));

    expect(
      await screen.findByText(/no manga were added\. 1 failed for another reason/i),
    ).toBeInTheDocument();
  });
});