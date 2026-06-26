import { fireEvent, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import Collections from "../../src/pages/Collections";
import { renderWithProviders } from "../testUtils";

const mockNavigate = vi.fn();
const mockMutateCreate = vi.fn();
const mockMutateDelete = vi.fn();

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
  useCollections: () => ({
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
  }),
  useCreateCollection: () => ({
    mutateAsync: mockMutateCreate,
    isPending: false,
  }),
  useDeleteCollection: () => ({
    mutateAsync: mockMutateDelete,
    isPending: false,
  }),
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe("Collections Page", () => {
  test("renders empty collections state", () => {
    renderWithProviders(<Collections />);

    expect(screen.getByRole("heading", { name: /collections/i })).toBeInTheDocument();
    expect(screen.getByText(/no collections yet/i)).toBeInTheDocument();
  });

  test("opens create collection form", () => {
    renderWithProviders(<Collections />);

    fireEvent.click(screen.getByRole("button", { name: /new collection/i }));

    expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/description/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^create$/i })).toBeInTheDocument();
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
});