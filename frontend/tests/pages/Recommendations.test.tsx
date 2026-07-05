import { fireEvent, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import Recommendations from "../../src/pages/Recommendations";
import { renderWithProviders } from "../testUtils";

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),

  useCollectionRecommendations: vi.fn(),
  useQueryListRecommendations: vi.fn(),

  collectionQuery: {
    data: undefined as unknown,
    isLoading: false,
    isError: false,
    isFetching: false,
  },

  queryListQuery: {
    data: undefined as unknown,
    isLoading: false,
    isError: false,
    isFetching: false,
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

vi.mock("../../src/hooks/useRecommendations", () => ({
  useCollectionRecommendations: (args: unknown) =>
    mocks.useCollectionRecommendations(args),
  useQueryListRecommendations: (args: unknown) =>
    mocks.useQueryListRecommendations(args),
}));

const recommendationPage = {
  total_results: 2,
  page: 1,
  size: 25,
  items: [
    {
      manga_id: 10,
      title: "Naruto",
      cover_image_url: null,
      external_average_rating: 4.5,
      recommendation_score: 12,
      genres: [],
    },
    {
      manga_id: 20,
      title: "One Piece",
      cover_image_url: null,
      external_average_rating: 4.8,
      recommendation_score: 10,
      genres: [],
    },
  ],
};

function renderRecommendations(
  initialEntry:
    | string
    | {
        pathname: string;
        search?: string;
        state?: unknown;
      } = "/recommendations"
) {
  return renderWithProviders(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/recommendations" element={<Recommendations />} />
      </Routes>
    </MemoryRouter>,
    { withRouter: false }
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  sessionStorage.clear();

  mocks.collectionQuery = {
    data: recommendationPage,
    isLoading: false,
    isError: false,
    isFetching: false,
  };

  mocks.queryListQuery = {
    data: recommendationPage,
    isLoading: false,
    isError: false,
    isFetching: false,
  };

  mocks.useCollectionRecommendations.mockImplementation(
    () => mocks.collectionQuery
  );

  mocks.useQueryListRecommendations.mockImplementation(
    () => mocks.queryListQuery
  );
});

describe("Recommendations Page", () => {
  test("shows empty source state when no collection or selected manga are provided", () => {
    renderRecommendations();

    expect(
      screen.getByRole("heading", { name: /recommendations/i })
    ).toBeInTheDocument();

    expect(
      screen.getByText(/no recommendation source selected/i)
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        /select manga from search or choose a collection to generate recommendations/i
      )
    ).toBeInTheDocument();
  });

  test("navigates to search from empty source state", () => {
    renderRecommendations();

    fireEvent.click(screen.getByRole("button", { name: /go to search/i }));

    expect(mocks.navigate).toHaveBeenCalledWith("/search");
  });

  test("loads recommendations from a collection id query param", async () => {
    renderRecommendations("/recommendations?collectionId=1");

    expect(
      await screen.findByText(/based on collection/i)
    ).toBeInTheDocument();

    expect(await screen.findByText(/naruto/i)).toBeInTheDocument();
    expect(await screen.findByText(/one piece/i)).toBeInTheDocument();

    expect(mocks.useCollectionRecommendations).toHaveBeenCalledWith(
      expect.objectContaining({
        collectionId: 1,
        enabled: true,
        params: expect.objectContaining({
          page: 1,
          size: 25,
          order_by: "score",
          order_dir: "desc",
        }),
      })
    );
  });

  test("loads recommendations from selected manga in router state", async () => {
    renderRecommendations({
      pathname: "/recommendations",
      state: {
        mangaIds: [10, 20],
      },
    });

    expect(
      await screen.findByText(/based on selected manga/i)
    ).toBeInTheDocument();

    expect(await screen.findByText(/naruto/i)).toBeInTheDocument();

    expect(mocks.useQueryListRecommendations).toHaveBeenCalledWith(
      expect.objectContaining({
        payload: {
          manga_ids: [10, 20],
        },
        enabled: true,
        params: expect.objectContaining({
          page: 1,
          size: 25,
          order_by: "score",
          order_dir: "desc",
        }),
      })
    );
  });

  test("loads recommendations from sessionStorage when router state is missing", async () => {
    sessionStorage.setItem("recommendationSeedIds", "[10,20]");

    renderRecommendations();

    expect(
      await screen.findByText(/based on selected manga/i)
    ).toBeInTheDocument();

    expect(mocks.useQueryListRecommendations).toHaveBeenCalledWith(
      expect.objectContaining({
        payload: {
          manga_ids: [10, 20],
        },
        enabled: true,
      })
    );
  });

  test("router state selected manga ids take priority over sessionStorage ids", async () => {
    sessionStorage.setItem("recommendationSeedIds", "[999]");

    renderRecommendations({
      pathname: "/recommendations",
      state: {
        mangaIds: [10, 20],
      },
    });

    await screen.findByText(/based on selected manga/i);

    expect(mocks.useQueryListRecommendations).toHaveBeenCalledWith(
      expect.objectContaining({
        payload: {
          manga_ids: [10, 20],
        },
      })
    );
  });

  test("shows loading state", () => {
    mocks.collectionQuery = {
      data: undefined,
      isLoading: true,
      isError: false,
      isFetching: true,
    };

    renderRecommendations("/recommendations?collectionId=1");

    expect(screen.getByText(/loading recommendations/i)).toBeInTheDocument();
  });

  test("shows error state", () => {
    mocks.collectionQuery = {
      data: undefined,
      isLoading: false,
      isError: true,
      isFetching: false,
    };

    renderRecommendations("/recommendations?collectionId=1");

    expect(
      screen.getByText(/failed to load recommendations/i)
    ).toBeInTheDocument();
  });

  test("shows no results when recommendation source returns empty items", () => {
    mocks.collectionQuery = {
      data: {
        total_results: 0,
        page: 1,
        size: 25,
        items: [],
      },
      isLoading: false,
      isError: false,
      isFetching: false,
    };

    renderRecommendations("/recommendations?collectionId=1");

    expect(screen.getByText(/no results/i)).toBeInTheDocument();
  });

  test("navigates back", () => {
    renderRecommendations("/recommendations?collectionId=1");

    fireEvent.click(screen.getByRole("button", { name: /back/i }));

    expect(mocks.navigate).toHaveBeenCalledWith(-1);
  });

  test("updates page when clicking next", async () => {
    mocks.collectionQuery = {
      data: {
        ...recommendationPage,
        total_results: 50,
        page: 1,
        size: 25,
      },
      isLoading: false,
      isError: false,
      isFetching: false,
    };

    renderRecommendations("/recommendations?collectionId=1");

    fireEvent.click(screen.getByRole("button", { name: /next/i }));

    await waitFor(() => {
      expect(mocks.useCollectionRecommendations).toHaveBeenLastCalledWith(
        expect.objectContaining({
          params: expect.objectContaining({
            page: 2,
          }),
        })
      );
    });
  });

  test("disables prev on first page", () => {
    renderRecommendations("/recommendations?collectionId=1");

    expect(screen.getByRole("button", { name: /prev/i })).toBeDisabled();
  });
});