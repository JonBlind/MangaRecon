import { fireEvent, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import Collections from "../../src/pages/Collections";
import { renderWithProviders } from "../testUtils";

const mockNavigate = vi.fn();
const mockMutateCreate = vi.fn();
const mockMutateDelete = vi.fn();
const mockUseCollectionsParams = vi.fn();

let mockDeletePending = false;
let mockCollectionsQuery = {
  data: {
    total_results: 0,
    page: 1,
    size: 10,
    items: [] as Array<{
      collection_id: number;
      collection_name: string;
      description: string | null;
      created_at: string;
    }>,
  },
  isLoading: false,
  isFetching: false,
  isError: false,
  error: null as unknown,
};

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
  useCollections: (params: unknown) => {
  mockUseCollectionsParams(params);
  return mockCollectionsQuery;
},
  useCreateCollection: () => ({
    mutateAsync: mockMutateCreate,
    isPending: false,
  }),
  useDeleteCollection: () => ({
    mutateAsync: mockMutateDelete,
    isPending: mockDeletePending,
  }),
}));

beforeEach(() => {
  vi.clearAllMocks();
  mockDeletePending = false;

  mockCollectionsQuery = {
    data: {
      total_results: 0,
      page: 1,
      size: 10,
      items: [],
    },
    isLoading: false,
    isFetching: false,
    isError: false,
    error: null,
  };

  mockMutateCreate.mockResolvedValue({
    collection_id: 123,
    collection_name: "Favorites",
    description: "My favorites",
  });

  mockMutateDelete.mockResolvedValue(undefined);
});

describe("Collections Page", () => {
  test("renders empty collections state", () => {
    renderWithProviders(<Collections />);

    expect(
      screen.getByRole("heading", { name: /collections/i })
    ).toBeInTheDocument();

    expect(screen.getByText(/no collections yet/i)).toBeInTheDocument();
  });

  test("shows loading state", () => {
    mockCollectionsQuery = {
      data: null as any,
      isLoading: true,
      isFetching: false,
      isError: false,
      error: null,
    };

    renderWithProviders(<Collections />);

    expect(screen.getByText(/loading collections/i)).toBeInTheDocument();
  });

  test("shows error state with provided message", () => {
    mockCollectionsQuery = {
      data: null as any,
      isLoading: false,
      isFetching: false,
      isError: true,
      error: new Error("Failed hard"),
    };

    renderWithProviders(<Collections />);

    expect(screen.getByText(/failed hard/i)).toBeInTheDocument();
  });

  test("shows fallback error state", () => {
    mockCollectionsQuery = {
      data: null as any,
      isLoading: false,
      isFetching: false,
      isError: true,
      error: null,
    };

    renderWithProviders(<Collections />);

    expect(
      screen.getByText(/failed to load collections/i)
    ).toBeInTheDocument();
  });

  test("opens create collection form", () => {
    renderWithProviders(<Collections />);

    fireEvent.click(screen.getByRole("button", { name: /new collection/i }));

    expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/description/i)).toBeInTheDocument();

    expect(
      screen.getByRole("button", { name: /^create$/i })
    ).toBeInTheDocument();
  });

  test("create button is disabled when name is empty", () => {
    renderWithProviders(<Collections />);

    fireEvent.click(screen.getByRole("button", { name: /new collection/i }));

    expect(screen.getByRole("button", { name: /^create$/i })).toBeDisabled();
  });

  test("creates collection and navigates to detail page", async () => {
    mockMutateCreate.mockResolvedValueOnce({
      collection_id: 123,
      collection_name: "Favorites",
      description: "My favorites",
    });

    renderWithProviders(<Collections />);

    fireEvent.click(screen.getByRole("button", { name: /new collection/i }));

    fireEvent.change(screen.getByLabelText(/name/i), {
      target: { value: "Favorites" },
    });

    fireEvent.change(screen.getByLabelText(/description/i), {
      target: { value: "My favorites" },
    });

    fireEvent.click(screen.getByRole("button", { name: /^create$/i }));

    await waitFor(() => {
      expect(mockMutateCreate).toHaveBeenCalledWith({
        collection_name: "Favorites",
        description: "My favorites",
      });
    });

    expect(mockNavigate).toHaveBeenCalledWith("/collections/123");
  });

  test("trims collection name and converts blank description to null", async () => {
    renderWithProviders(<Collections />);

    fireEvent.click(screen.getByRole("button", { name: /new collection/i }));

    fireEvent.change(screen.getByLabelText(/name/i), {
      target: { value: "   Favorites   " },
    });

    fireEvent.change(screen.getByLabelText(/description/i), {
      target: { value: "   " },
    });

    fireEvent.click(screen.getByRole("button", { name: /^create$/i }));

    await waitFor(() => {
      expect(mockMutateCreate).toHaveBeenCalledWith({
        collection_name: "Favorites",
        description: null,
      });
    });
  });

  test("shows create error feedback", async () => {
    mockMutateCreate.mockRejectedValueOnce(new Error("Duplicate collection"));

    renderWithProviders(<Collections />);

    fireEvent.click(screen.getByRole("button", { name: /new collection/i }));

    fireEvent.change(screen.getByLabelText(/name/i), {
      target: { value: "Favorites" },
    });

    fireEvent.click(screen.getByRole("button", { name: /^create$/i }));

    expect(
      await screen.findByText(/duplicate collection/i)
    ).toBeInTheDocument();
  });

  test("shows fallback create error feedback", async () => {
    mockMutateCreate.mockRejectedValueOnce({});

    renderWithProviders(<Collections />);

    fireEvent.click(screen.getByRole("button", { name: /new collection/i }));

    fireEvent.change(screen.getByLabelText(/name/i), {
      target: { value: "Favorites" },
    });

    fireEvent.click(screen.getByRole("button", { name: /^create$/i }));

    expect(
      await screen.findByText(/failed to create collection/i)
    ).toBeInTheDocument();
  });

  test("renders existing collections", () => {
    mockCollectionsQuery = {
      data: {
        total_results: 2,
        page: 1,
        size: 10,
        items: [
          {
            collection_id: 1,
            collection_name: "Favorites",
            description: "My favorite manga",
            created_at: "2026-01-01T00:00:00Z",
          },
          {
            collection_id: 2,
            collection_name: "To Read",
            description: null,
            created_at: "2026-01-02T00:00:00Z",
          },
        ],
      },
      isLoading: false,
      isFetching: false,
      isError: false,
      error: null,
    };

    renderWithProviders(<Collections />);

    expect(screen.getByText(/2 collections/i)).toBeInTheDocument();
    expect(screen.getByText(/favorites/i)).toBeInTheDocument();
    expect(screen.getByText(/my favorite manga/i)).toBeInTheDocument();
    expect(screen.getByText(/to read/i)).toBeInTheDocument();
    expect(screen.getByText(/no description/i)).toBeInTheDocument();
  });

  test("clicking a collection navigates to detail page", () => {
    mockCollectionsQuery = {
      data: {
        total_results: 1,
        page: 1,
        size: 10,
        items: [
          {
            collection_id: 1,
            collection_name: "Favorites",
            description: "My favorite manga",
            created_at: "2026-01-01T00:00:00Z",
          },
        ],
      },
      isLoading: false,
      isFetching: false,
      isError: false,
      error: null,
    };

    renderWithProviders(<Collections />);

    fireEvent.click(screen.getByRole("button", { name: /favorites/i }));

    expect(mockNavigate).toHaveBeenCalledWith("/collections/1");
  });

  test("opens delete confirmation without navigating", () => {
    mockCollectionsQuery = {
      data: {
        total_results: 1,
        page: 1,
        size: 10,
        items: [
          {
            collection_id: 1,
            collection_name: "Favorites",
            description: "My favorite manga",
            created_at: "2026-01-01T00:00:00Z",
          },
        ],
      },
      isLoading: false,
      isFetching: false,
      isError: false,
      error: null,
    };

    renderWithProviders(<Collections />);

    fireEvent.click(screen.getByTitle("Delete collection"));

    expect(screen.getByText(/this cannot be undone/i)).toBeInTheDocument();

    expect(
      screen.getByRole("button", { name: /confirm delete/i })
    ).toBeInTheDocument();

    expect(mockNavigate).not.toHaveBeenCalled();
  });

  test("cancels delete confirmation", () => {
    mockCollectionsQuery = {
      data: {
        total_results: 1,
        page: 1,
        size: 10,
        items: [
          {
            collection_id: 1,
            collection_name: "Favorites",
            description: "My favorite manga",
            created_at: "2026-01-01T00:00:00Z",
          },
        ],
      },
      isLoading: false,
      isFetching: false,
      isError: false,
      error: null,
    };

    renderWithProviders(<Collections />);

    fireEvent.click(screen.getByTitle("Delete collection"));
    fireEvent.click(screen.getByRole("button", { name: /^cancel$/i }));

    expect(screen.queryByText(/this cannot be undone/i)).not.toBeInTheDocument();
  });

  test("deletes collection and shows success feedback", async () => {
    mockCollectionsQuery = {
      data: {
        total_results: 1,
        page: 1,
        size: 10,
        items: [
          {
            collection_id: 1,
            collection_name: "Favorites",
            description: "My favorite manga",
            created_at: "2026-01-01T00:00:00Z",
          },
        ],
      },
      isLoading: false,
      isFetching: false,
      isError: false,
      error: null,
    };

    renderWithProviders(<Collections />);

    fireEvent.click(screen.getByTitle("Delete collection"));
    fireEvent.click(screen.getByRole("button", { name: /confirm delete/i }));

    await waitFor(() => {
      expect(mockMutateDelete).toHaveBeenCalledWith(1);
    });

    expect(
      await screen.findByText(/collection "favorites" was deleted/i)
    ).toBeInTheDocument();
  });

  test("shows delete error feedback", async () => {
    mockMutateDelete.mockRejectedValueOnce(new Error("Delete failed"));

    mockCollectionsQuery = {
      data: {
        total_results: 1,
        page: 1,
        size: 10,
        items: [
          {
            collection_id: 1,
            collection_name: "Favorites",
            description: "My favorite manga",
            created_at: "2026-01-01T00:00:00Z",
          },
        ],
      },
      isLoading: false,
      isFetching: false,
      isError: false,
      error: null,
    };

    renderWithProviders(<Collections />);

    fireEvent.click(screen.getByTitle("Delete collection"));
    fireEvent.click(screen.getByRole("button", { name: /confirm delete/i }));

    expect(await screen.findByText(/delete failed/i)).toBeInTheDocument();
  });

  test("opens a collection with the Enter key", () => {
    mockCollectionsQuery = {
      data: {
        total_results: 1,
        page: 1,
        size: 10,
        items: [
          {
            collection_id: 1,
            collection_name: "Favorites",
            description: "My favorite manga",
            created_at: "2026-01-01T00:00:00Z",
          },
        ],
      },
      isLoading: false,
      isFetching: false,
      isError: false,
      error: null,
    };

    renderWithProviders(<Collections />);

    fireEvent.keyDown(
      screen.getByRole("button", {
        name: /open collection favorites/i,
      }),
      {
        key: "Enter",
      }
    );

    expect(mockNavigate).toHaveBeenCalledWith("/collections/1");
  });

  test("opens a collection with the Space key", () => {
    mockCollectionsQuery = {
      data: {
        total_results: 1,
        page: 1,
        size: 10,
        items: [
          {
            collection_id: 1,
            collection_name: "Favorites",
            description: "My favorite manga",
            created_at: "2026-01-01T00:00:00Z",
          },
        ],
      },
      isLoading: false,
      isFetching: false,
      isError: false,
      error: null,
    };

    renderWithProviders(<Collections />);

    fireEvent.keyDown(
      screen.getByRole("button", {
        name: /open collection favorites/i,
      }),
      {
        key: " ",
      }
    );

    expect(mockNavigate).toHaveBeenCalledWith("/collections/1");
  });

  test("does not navigate when clicking delete confirmation text", () => {
    mockCollectionsQuery = {
      data: {
        total_results: 1,
        page: 1,
        size: 10,
        items: [
          {
            collection_id: 1,
            collection_name: "Favorites",
            description: "My favorite manga",
            created_at: "2026-01-01T00:00:00Z",
          },
        ],
      },
      isLoading: false,
      isFetching: false,
      isError: false,
      error: null,
    };

    renderWithProviders(<Collections />);

    fireEvent.click(screen.getByTitle("Delete collection"));

    fireEvent.click(screen.getByText(/this cannot be undone/i));

    expect(mockNavigate).not.toHaveBeenCalled();
  });

  test("moves to next page", async () => {
    mockCollectionsQuery = {
      data: {
        total_results: 25,
        page: 1,
        size: 10,
        items: [
          {
            collection_id: 1,
            collection_name: "Favorites",
            description: "My favorite manga",
            created_at: "2026-01-01T00:00:00Z",
          },
        ],
      },
      isLoading: false,
      isFetching: false,
      isError: false,
      error: null,
    };

    renderWithProviders(<Collections />);

    fireEvent.click(screen.getByRole("button", { name: /next/i }));

    await waitFor(() => {
      expect(mockUseCollectionsParams).toHaveBeenLastCalledWith({
        page: 2,
        size: 10,
        order: "desc",
      });
    });
  });

  test("moves back to previous page", async () => {
    mockCollectionsQuery = {
      data: {
        total_results: 25,
        page: 1,
        size: 10,
        items: [
          {
            collection_id: 1,
            collection_name: "Favorites",
            description: "My favorite manga",
            created_at: "2026-01-01T00:00:00Z",
          },
        ],
      },
      isLoading: false,
      isFetching: false,
      isError: false,
      error: null,
    };

    renderWithProviders(<Collections />);

    fireEvent.click(screen.getByRole("button", { name: /next/i }));

    await waitFor(() => {
      expect(mockUseCollectionsParams).toHaveBeenLastCalledWith(
        expect.objectContaining({ page: 2 })
      );
    });

    fireEvent.click(screen.getByRole("button", { name: /prev/i }));

    await waitFor(() => {
      expect(mockUseCollectionsParams).toHaveBeenLastCalledWith({
        page: 1,
        size: 10,
        order: "desc",
      });
    });
  });

  test("disables pagination while collections are fetching", () => {
    mockCollectionsQuery = {
      data: {
        total_results: 25,
        page: 1,
        size: 10,
        items: [
          {
            collection_id: 1,
            collection_name: "Favorites",
            description: "My favorite manga",
            created_at: "2026-01-01T00:00:00Z",
          },
        ],
      },
      isLoading: false,
      isFetching: true,
      isError: false,
      error: null,
    };

    renderWithProviders(<Collections />);

    expect(screen.getByRole("button", { name: /prev/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /next/i })).toBeDisabled();
  });

  test("moves back one page after deleting the only item on a later page", async () => {
    mockCollectionsQuery = {
      data: {
        total_results: 11,
        page: 2,
        size: 10,
        items: [
          {
            collection_id: 11,
            collection_name: "Last Collection",
            description: null,
            created_at: "2026-01-11T00:00:00Z",
          },
        ],
      },
      isLoading: false,
      isFetching: false,
      isError: false,
      error: null,
    };

    renderWithProviders(<Collections />);

    fireEvent.click(screen.getByRole("button", { name: /next/i }));

    await waitFor(() => {
      expect(mockUseCollectionsParams).toHaveBeenLastCalledWith(
        expect.objectContaining({ page: 2 })
      );
    });

    fireEvent.click(screen.getByTitle("Delete collection"));

    fireEvent.click(
      screen.getByRole("button", {
        name: /^confirm delete$/i,
      })
    );

    await waitFor(() => {
      expect(mockMutateDelete).toHaveBeenCalledWith(11);
    });

    await waitFor(() => {
      expect(mockUseCollectionsParams).toHaveBeenLastCalledWith({
        page: 1,
        size: 10,
        order: "desc",
      });
    });
  });
});