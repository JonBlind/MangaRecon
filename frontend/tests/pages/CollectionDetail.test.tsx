import { fireEvent, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import CollectionDetail from "../../src/pages/CollectionDetail";
import { renderWithProviders } from "../testUtils";

const mockNavigate = vi.fn();
const mockRemoveManga = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>(
    "react-router-dom"
  );

  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

vi.mock("../../src/hooks/useCollections", () => ({
  useCollection: () => ({
    data: {
      collection_id: 1,
      collection_name: "Favorites",
      description: "My favorite manga",
    },
    isLoading: false,
    isError: false,
  }),

  useCollectionManga: () => ({
    data: {
      total_results: 2,
      page: 1,
      size: 20,
      items: [
        { manga_id: 10, title: "One Piece" },
        { manga_id: 20, title: "Naruto" },
      ],
    },
    isLoading: false,
    isError: false,
  }),

  useRemoveMangaFromCollection: () => ({
    mutateAsync: mockRemoveManga,
    isPending: false,
  }),
}));

function renderCollectionDetail() {
  return renderWithProviders(
    <MemoryRouter initialEntries={["/collections/1"]}>
      <Routes>
        <Route path="/collections/:id" element={<CollectionDetail />} />
        <Route path="/collections" element={<div>Collections Page</div>} />
      </Routes>
    </MemoryRouter>,
    { withRouter: false }
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("CollectionDetail Page", () => {
  test("renders collection info and manga list", () => {
    renderCollectionDetail();

    expect(
      screen.getByRole("heading", { name: /favorites/i })
    ).toBeInTheDocument();

    expect(screen.getByText(/my favorite manga/i)).toBeInTheDocument();
    expect(screen.getByText(/one piece/i)).toBeInTheDocument();
    expect(screen.getByText(/naruto/i)).toBeInTheDocument();
  });

  test("removes manga from collection", async () => {
    mockRemoveManga.mockResolvedValueOnce({});

    renderCollectionDetail();

    fireEvent.click(
        screen.getAllByRole("button", {
        name: /remove from collection/i,
        })[0]
    );

    fireEvent.click(
        screen.getByRole("button", {
        name: /^remove$/i,
        })
    );

    await waitFor(() => {
        expect(mockRemoveManga).toHaveBeenCalledWith(10);
    });
  });

  test("navigates back to collections", () => {
    renderCollectionDetail();

    fireEvent.click(
      screen.getByRole("button", {
        name: /back to collections/i,
      })
    );

    expect(mockNavigate).toHaveBeenCalledWith("/collections");
  });

  test("navigates to recommendations page", () => {
    renderCollectionDetail();

    fireEvent.click(
      screen.getByRole("button", {
        name: /get recommendations/i,
      })
    );

    expect(mockNavigate).toHaveBeenCalledWith(
      "/recommendations?collectionId=1"
    );
  });
});