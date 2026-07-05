import { fireEvent, screen, waitFor } from "@testing-library/react";
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
  const actual = await vi.importActual<typeof import("react-router-dom")>(
    "react-router-dom"
  );

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

    expect(
      screen.getByRole("heading", { name: /^search$/i })
    ).toBeInTheDocument();

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

  test("updates search when title input changes", async () => {
    renderWithProviders(<Search />);

    fireEvent.change(screen.getByPlaceholderText(/e\.g\. naruto/i), {
      target: { value: "Bleach" },
    });

    await waitFor(() => {
      expect(mocks.searchMangas).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "Bleach",
          page: 1,
          size: 25,
          order_by: "title",
          order_dir: "asc",
        })
      );
    });
  });

  test("selects a manga result", async () => {
    renderWithProviders(<Search />);

    fireEvent.click(
      await screen.findByRole("button", { name: /select naruto/i })
    );

    expect(mocks.toggleSelection).toHaveBeenCalledWith(
      expect.objectContaining({
        manga_id: 10,
        title: "Naruto",
      })
    );
  });

  test("opens auth modal when unauthenticated user tries to save selected manga", async () => {
    mocks.selectedIds = [10];
    mocks.selectedCount = 1;

    renderWithProviders(<Search />);

    fireEvent.click(screen.getByRole("button", { name: /sign in to save/i }));

    expect(await screen.findByText(/sign in required/i)).toBeInTheDocument();
    expect(
      screen.getByText(/you need an account to save manga to a collection/i)
    ).toBeInTheDocument();
  });

  test("navigates to recommendations with selected manga ids", () => {
    mocks.selectedIds = [10, 20];
    mocks.selectedCount = 2;

    renderWithProviders(<Search />);

    fireEvent.click(
      screen.getByRole("button", { name: /get recommendations/i })
    );

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

    renderWithProviders(<Search />);

    fireEvent.click(screen.getByRole("button", { name: /add to collection/i }));

    expect(
      await screen.findByRole("heading", { name: /add to collection/i })
    ).toBeInTheDocument();

    fireEvent.change(screen.getByDisplayValue("Select a collection"), {
      target: { value: "1" },
    });

    fireEvent.click(screen.getByRole("button", { name: /^add$/i }));

    await waitFor(() => {
      expect(mocks.addMangasBulkToCollection).toHaveBeenCalledWith(1, [
        10, 20,
      ]);
    });

    await waitFor(() => {
      expect(mocks.removeSelectedIds).toHaveBeenCalledWith([10, 20]);
    });

    expect(
      await screen.findByText(/2 manga added to collection/i)
    ).toBeInTheDocument();
  });
});