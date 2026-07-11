import { fireEvent, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import CollectionPickerModal from "../../src/components/CollectionPickerModal";
import { renderWithProviders } from "../testUtils";

const mocks = vi.hoisted(() => ({
  useCollections: vi.fn(),
  useCreateCollection: vi.fn(),
  createMutateAsync: vi.fn(),
}));

vi.mock("../../src/hooks/useCollections", () => ({
  useCollections: (params: unknown) => mocks.useCollections(params),
  useCreateCollection: () => mocks.useCreateCollection(),
}));

const onClose = vi.fn();
const onConfirm = vi.fn();

const collectionsPage = {
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
};

function renderModal(props = {}) {
  return renderWithProviders(
    <CollectionPickerModal
      open={true}
      onClose={onClose}
      onConfirm={onConfirm}
      selectedCount={2}
      {...props}
    />
  );
}

beforeEach(() => {
  vi.clearAllMocks();

  mocks.useCollections.mockReturnValue({
    data: collectionsPage,
    isLoading: false,
    isError: false,
  });

  mocks.useCreateCollection.mockReturnValue({
    mutateAsync: mocks.createMutateAsync,
    isPending: false,
  });

  mocks.createMutateAsync.mockResolvedValue({
    collection_id: 2,
    collection_name: "New Collection",
    description: null,
    created_at: "2026-01-01T00:00:00Z",
  });
});

describe("CollectionPickerModal", () => {
  test("does not render when closed", () => {
    renderModal({ open: false });

    expect(
      screen.queryByRole("heading", { name: /add to collection/i })
    ).not.toBeInTheDocument();
  });

  test("renders existing collection mode by default", () => {
    renderModal();

    expect(
      screen.getByRole("heading", { name: /add to collection/i })
    ).toBeInTheDocument();

    expect(
      screen.getByText(/add 2 selected manga to a collection/i)
    ).toBeInTheDocument();

    expect(screen.getByLabelText(/collection/i)).toBeInTheDocument();
    expect(screen.getByText(/favorites/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^add$/i })).toBeDisabled();
  });

  test("confirms existing collection selection", () => {
    renderModal();

    fireEvent.change(screen.getByLabelText(/collection/i), {
      target: { value: "1" },
    });

    fireEvent.click(screen.getByRole("button", { name: /^add$/i }));

    expect(onConfirm).toHaveBeenCalledWith(1);
  });

  test("shows loading collections state", () => {
    mocks.useCollections.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    });

    renderModal();

    expect(screen.getByText(/loading collections/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^add$/i })).toBeDisabled();
  });

  test("shows collection load error state", () => {
    mocks.useCollections.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    });

    renderModal();

    expect(
      screen.getByText(/failed to load collections/i)
    ).toBeInTheDocument();

    expect(screen.getByRole("button", { name: /^add$/i })).toBeDisabled();
  });

  test("switches to create mode", () => {
    renderModal();

    fireEvent.click(
      screen.getByRole("button", { name: /create new collection/i })
    );

    expect(screen.getByLabelText(/collection name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/description/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /create and add/i })
    ).toBeDisabled();
  });

  test("creates collection and confirms created collection id", async () => {
    renderModal();

    fireEvent.click(
      screen.getByRole("button", { name: /create new collection/i })
    );

    fireEvent.change(screen.getByLabelText(/collection name/i), {
      target: { value: "  New Collection  " },
    });

    fireEvent.change(screen.getByLabelText(/description/i), {
      target: { value: "  Optional description  " },
    });

    fireEvent.click(screen.getByRole("button", { name: /create and add/i }));

    await waitFor(() => {
      expect(mocks.createMutateAsync).toHaveBeenCalledWith({
        collection_name: "New Collection",
        description: "Optional description",
      });
    });

    expect(onConfirm).toHaveBeenCalledWith(2);
  });

  test("creates collection with null description when description is blank", async () => {
    renderModal();

    fireEvent.click(
      screen.getByRole("button", { name: /create new collection/i })
    );

    fireEvent.change(screen.getByLabelText(/collection name/i), {
      target: { value: "New Collection" },
    });

    fireEvent.click(screen.getByRole("button", { name: /create and add/i }));

    await waitFor(() => {
      expect(mocks.createMutateAsync).toHaveBeenCalledWith({
        collection_name: "New Collection",
        description: null,
      });
    });

    expect(onConfirm).toHaveBeenCalledWith(2);
  });

  test("automatically switches to create mode when user has no collections", async () => {
    mocks.useCollections.mockReturnValue({
      data: {
        total_results: 0,
        page: 1,
        size: 100,
        items: [],
      },
      isLoading: false,
      isError: false,
    });

    renderModal();

    expect(
      await screen.findByLabelText(/collection name/i)
    ).toBeInTheDocument();

    expect(screen.queryByText(/no collections found/i)).not.toBeInTheDocument();
  });

  test("shows create collection error", async () => {
    mocks.createMutateAsync.mockRejectedValueOnce(
      new Error("Collection already exists.")
    );

    renderModal();

    fireEvent.click(
      screen.getByRole("button", { name: /create new collection/i })
    );

    fireEvent.change(screen.getByLabelText(/collection name/i), {
      target: { value: "Favorites" },
    });

    fireEvent.click(screen.getByRole("button", { name: /create and add/i }));

    expect(
      await screen.findByText(/collection already exists/i)
    ).toBeInTheDocument();

    expect(onConfirm).not.toHaveBeenCalled();
  });

  test("closes when cancel is clicked", () => {
    renderModal();

    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test("does not close with backdrop click while submitting", () => {
    renderModal({ isSubmitting: true });

    fireEvent.click(screen.getByText(/add 2 selected manga/i).closest(".fixed")!);

    expect(onClose).not.toHaveBeenCalled();
  });

  test("shows adding state while submitting", () => {
    renderModal({ isSubmitting: true });

    expect(screen.getByRole("button", { name: /adding/i })).toBeDisabled();
  });

  test("shows creating state while creating collection", () => {
    mocks.useCreateCollection.mockReturnValue({
      mutateAsync: mocks.createMutateAsync,
      isPending: true,
    });

    renderModal();

    fireEvent.click(
      screen.getByRole("button", { name: /create new collection/i })
    );

    expect(screen.getByRole("button", { name: /creating/i })).toBeDisabled();
  });
});