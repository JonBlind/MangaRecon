import { fireEvent, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import CollectionDetail from "../../src/pages/CollectionDetail";
import { renderWithProviders } from "../testUtils";

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  removeManga: vi.fn(),
  useCollectionMangaParams: vi.fn(),

  removePending: false,

  collectionQuery: {
    data: {
      collection_id: 1,
      collection_name: "Favorites",
      description: "My favorite manga",
    } as any,
    isLoading: false,
    isError: false,
    error: null as unknown,
  },

  mangaQuery: {
    data: {
      total_results: 2,
      page: 1,
      size: 20,
      items: [
        {
          manga_id: 10,
          title: "One Piece",
          description: "Pirate adventure",
          cover_image_url: null,
        },
        {
          manga_id: 20,
          title: "Naruto",
          description: null,
          cover_image_url: null,
        },
      ],
    } as any,
    isLoading: false,
    isFetching: false,
    isError: false,
    error: null as unknown,
  },
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

vi.mock("../../src/hooks/useCollections", () => ({
  useCollection: () => mocks.collectionQuery,

  useCollectionManga: (
    collectionId: number,
    params: {
      page: number;
      size: number;
      order: "asc" | "desc";
    }
  ) => {
    mocks.useCollectionMangaParams(collectionId, params);
    return mocks.mangaQuery;
  },

  useRemoveMangaFromCollection: () => ({
    mutateAsync: mocks.removeManga,
    isPending: mocks.removePending,
  }),
}));

function renderCollectionDetail(initialEntry = "/collections/1") {
  return renderWithProviders(
    <MemoryRouter initialEntries={[initialEntry]}>
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

  mocks.removePending = false;

  mocks.collectionQuery = {
    data: {
      collection_id: 1,
      collection_name: "Favorites",
      description: "My favorite manga",
    },
    isLoading: false,
    isError: false,
    error: null,
  };

  mocks.mangaQuery = {
    data: {
      total_results: 2,
      page: 1,
      size: 20,
      items: [
        {
          manga_id: 10,
          title: "One Piece",
          description: "Pirate adventure",
          cover_image_url: null,
        },
        {
          manga_id: 20,
          title: "Naruto",
          description: null,
          cover_image_url: null,
        },
      ],
    },
    isLoading: false,
    isFetching: false,
    isError: false,
    error: null,
  };

  mocks.removeManga.mockResolvedValue(undefined);
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
    expect(screen.getByText(/2 items/i)).toBeInTheDocument();
  });

  test("shows invalid collection state", () => {
    renderCollectionDetail("/collections/not-a-number");

    expect(
      screen.getByRole("heading", { name: /invalid collection/i })
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: /back to collections/i })
    );

    expect(mocks.navigate).toHaveBeenCalledWith("/collections");
  });

  test("shows collection loading state", () => {
    mocks.collectionQuery = {
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
    };

    renderCollectionDetail();

    expect(screen.getByText(/loading collection/i)).toBeInTheDocument();
  });

  test("shows collection error message", () => {
    mocks.collectionQuery = {
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error("Collection request failed"),
    };

    renderCollectionDetail();

    expect(
      screen.getByText(/collection request failed/i)
    ).toBeInTheDocument();
  });

  test("shows fallback collection error message", () => {
    mocks.collectionQuery = {
      data: undefined,
      isLoading: false,
      isError: true,
      error: null,
    };

    renderCollectionDetail();

    expect(
      screen.getByText(/failed to load collection/i)
    ).toBeInTheDocument();
  });

  test("shows fallback collection title and description", () => {
    mocks.collectionQuery = {
      data: undefined,
      isLoading: false,
      isError: false,
      error: null,
    };

    renderCollectionDetail();

    expect(
      screen.getByRole("heading", { name: /^collection$/i })
    ).toBeInTheDocument();

    expect(screen.getByText(/no description/i)).toBeInTheDocument();

    expect(
      screen.getByRole("button", { name: /get recommendations/i })
    ).toBeDisabled();
  });

  test("shows manga loading state", () => {
    mocks.mangaQuery = {
      data: undefined,
      isLoading: true,
      isFetching: false,
      isError: false,
      error: null,
    };

    renderCollectionDetail();

    expect(screen.getByText(/loading manga/i)).toBeInTheDocument();
  });

  test("shows manga error message", () => {
    mocks.mangaQuery = {
      data: undefined,
      isLoading: false,
      isFetching: false,
      isError: true,
      error: new Error("Manga request failed"),
    };

    renderCollectionDetail();

    expect(screen.getByText(/manga request failed/i)).toBeInTheDocument();
  });

  test("shows fallback manga error message", () => {
    mocks.mangaQuery = {
      data: undefined,
      isLoading: false,
      isFetching: false,
      isError: true,
      error: null,
    };

    renderCollectionDetail();

    expect(
      screen.getByText(/failed to load manga in this collection/i)
    ).toBeInTheDocument();
  });

  test("shows empty collection state", () => {
    mocks.mangaQuery = {
      data: {
        total_results: 0,
        page: 1,
        size: 20,
        items: [],
      },
      isLoading: false,
      isFetching: false,
      isError: false,
      error: null,
    };

    renderCollectionDetail();

    expect(screen.getByText(/this collection is empty/i)).toBeInTheDocument();
  });

  test("removes manga from collection", async () => {
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
      expect(mocks.removeManga).toHaveBeenCalledWith(10);
    });

    expect(
      await screen.findByText(/"one piece" was removed from the collection/i)
    ).toBeInTheDocument();
  });

  test("cancels tile removal", () => {
    renderCollectionDetail();

    fireEvent.click(
      screen.getAllByRole("button", {
        name: /remove from collection/i,
      })[0]
    );

    expect(
      screen.getByRole("button", { name: /^cancel$/i })
    ).toBeInTheDocument();

    expect(
      screen.getByRole("button", { name: /^remove$/i })
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /^cancel$/i }));

    expect(
      screen.queryByRole("button", { name: /^cancel$/i })
    ).not.toBeInTheDocument();

    expect(mocks.removeManga).not.toHaveBeenCalled();
  });

  test("shows remove error feedback", async () => {
    mocks.removeManga.mockRejectedValueOnce(new Error("Remove request failed"));

    renderCollectionDetail();

    fireEvent.click(
      screen.getAllByRole("button", {
        name: /remove from collection/i,
      })[0]
    );

    fireEvent.click(screen.getByRole("button", { name: /^remove$/i }));

    expect(
      await screen.findByText(/remove request failed/i)
    ).toBeInTheDocument();
  });

  test("shows fallback remove error feedback", async () => {
    mocks.removeManga.mockRejectedValueOnce({});

    renderCollectionDetail();

    fireEvent.click(
      screen.getAllByRole("button", {
        name: /remove from collection/i,
      })[0]
    );

    fireEvent.click(screen.getByRole("button", { name: /^remove$/i }));

    expect(
      await screen.findByText(/failed to remove manga/i)
    ).toBeInTheDocument();
  });

  test("switches to list view", () => {
    renderCollectionDetail();

    fireEvent.click(screen.getByRole("button", { name: /list view/i }));

    expect(
      screen.getByRole("link", { name: /one piece/i })
    ).toHaveAttribute("href", "/manga/10");

    expect(screen.getByText(/pirate adventure/i)).toBeInTheDocument();
    expect(screen.getByText(/no description/i)).toBeInTheDocument();
  });

  test("removes manga from list view", async () => {
    renderCollectionDetail();

    fireEvent.click(screen.getByRole("button", { name: /list view/i }));

    fireEvent.click(
      screen.getAllByRole("button", {
        name: /^remove$/i,
      })[0]
    );

    expect(
      screen.getByRole("button", { name: /confirm remove/i })
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", {
        name: /confirm remove/i,
      })
    );

    await waitFor(() => {
      expect(mocks.removeManga).toHaveBeenCalledWith(10);
    });
  });

  test("cancels manga removal from list view", () => {
    renderCollectionDetail();

    fireEvent.click(screen.getByRole("button", { name: /list view/i }));

    fireEvent.click(
      screen.getAllByRole("button", {
        name: /^remove$/i,
      })[0]
    );

    fireEvent.click(screen.getByRole("button", { name: /^cancel$/i }));

    expect(
      screen.queryByText(/remove one piece from this collection/i)
    ).not.toBeInTheDocument();

    expect(mocks.removeManga).not.toHaveBeenCalled();
  });

  test("switches back from list view to tile view", () => {
    renderCollectionDetail();

    fireEvent.click(screen.getByRole("button", { name: /list view/i }));
    fireEvent.click(screen.getByRole("button", { name: /tile view/i }));

    expect(
      screen.getAllByRole("button", {
        name: /remove from collection/i,
      })
    ).toHaveLength(2);
  });

  test("navigates back to collections", () => {
    renderCollectionDetail();

    fireEvent.click(
      screen.getByRole("button", {
        name: /back to collections/i,
      })
    );

    expect(mocks.navigate).toHaveBeenCalledWith("/collections");
  });

  test("navigates to recommendations page", () => {
    renderCollectionDetail();

    fireEvent.click(
      screen.getByRole("button", {
        name: /get recommendations/i,
      })
    );

    expect(mocks.navigate).toHaveBeenCalledWith(
      "/recommendations?collectionId=1"
    );
  });

  test("moves to next and previous manga pages", async () => {
    mocks.mangaQuery = {
      data: {
        total_results: 45,
        page: 1,
        size: 20,
        items: [
          {
            manga_id: 10,
            title: "One Piece",
            description: null,
            cover_image_url: null,
          },
        ],
      },
      isLoading: false,
      isFetching: false,
      isError: false,
      error: null,
    };

    renderCollectionDetail();

    fireEvent.click(screen.getByRole("button", { name: /next/i }));

    await waitFor(() => {
      expect(mocks.useCollectionMangaParams).toHaveBeenLastCalledWith(1, {
        page: 2,
        size: 20,
        order: "desc",
      });
    });

    fireEvent.click(screen.getByRole("button", { name: /prev/i }));

    await waitFor(() => {
      expect(mocks.useCollectionMangaParams).toHaveBeenLastCalledWith(1, {
        page: 1,
        size: 20,
        order: "desc",
      });
    });
  });

  test("disables pagination while manga is fetching", () => {
    mocks.mangaQuery = {
      data: {
        total_results: 45,
        page: 1,
        size: 20,
        items: [
          {
            manga_id: 10,
            title: "One Piece",
            description: null,
            cover_image_url: null,
          },
        ],
      },
      isLoading: false,
      isFetching: true,
      isError: false,
      error: null,
    };

    renderCollectionDetail();

    expect(screen.getByRole("button", { name: /prev/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /next/i })).toBeDisabled();
  });

  test("moves back one page after removing the final item on a later page", async () => {
    mocks.mangaQuery = {
      data: {
        total_results: 21,
        page: 1,
        size: 20,
        items: [
          {
            manga_id: 21,
            title: "Final Manga",
            description: null,
            cover_image_url: null,
          },
        ],
      },
      isLoading: false,
      isFetching: false,
      isError: false,
      error: null,
    };

    renderCollectionDetail();

    fireEvent.click(screen.getByRole("button", { name: /next/i }));

    await waitFor(() => {
      expect(mocks.useCollectionMangaParams).toHaveBeenLastCalledWith(1, {
        page: 2,
        size: 20,
        order: "desc",
      });
    });

    fireEvent.click(
      screen.getByRole("button", {
        name: /remove from collection/i,
      })
    );

    fireEvent.click(screen.getByRole("button", { name: /^remove$/i }));

    await waitFor(() => {
      expect(mocks.removeManga).toHaveBeenCalledWith(21);
    });

    await waitFor(() => {
      expect(mocks.useCollectionMangaParams).toHaveBeenLastCalledWith(1, {
        page: 1,
        size: 20,
        order: "desc",
      });
    });
  });
});