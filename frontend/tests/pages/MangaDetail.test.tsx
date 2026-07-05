import { fireEvent, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import MangaDetail from "../../src/pages/MangaDetail";
import { renderWithProviders } from "../testUtils";

const mocks = vi.hoisted(() => ({
  useManga: vi.fn(),
  useMe: vi.fn(),
  useCollections: vi.fn(),
  useAddMangaToCollection: vi.fn(),

  mutateAsync: vi.fn(),
}));

vi.mock("../../src/hooks/useManga", () => ({
  useManga: (mangaId: number) => mocks.useManga(mangaId),
}));

vi.mock("../../src/hooks/useMe", () => ({
  useMe: () => mocks.useMe(),
}));

vi.mock("../../src/hooks/useCollections", () => ({
  useCollections: (params: unknown) => mocks.useCollections(params),
  useAddMangaToCollection: (collectionId: number) =>
    mocks.useAddMangaToCollection(collectionId),
}));

const mangaDetail = {
  manga_id: 10,
  title: "Naruto",
  description: "A ninja story.",
  published_date: "1999-09-21",
  average_rating: 4.2,
  external_average_rating: 4.7,
  author_id: 1,
  cover_image_url: "https://example.com/naruto.jpg",
  demographics: [{ demographic_id: 1, demographic_name: "Shounen" }],
  genres: [{ genre_id: 1, genre_name: "Action" }],
  tags: [{ tag_id: 1, tag_name: "Adventure" }],
};

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

function renderMangaDetail(
  initialEntry:
    | string
    | {
        pathname: string;
        state?: unknown;
      } = "/manga/10"
) {
  return renderWithProviders(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/manga/:id" element={<MangaDetail />} />
      </Routes>
    </MemoryRouter>,
    { withRouter: false }
  );
}

beforeEach(() => {
  vi.clearAllMocks();

  mocks.useManga.mockReturnValue({
    data: mangaDetail,
    isPending: false,
    isError: false,
  });

  mocks.useMe.mockReturnValue({
    data: null,
    isPending: false,
  });

  mocks.useCollections.mockReturnValue({
    data: collectionsPage,
    isLoading: false,
  });

  mocks.useAddMangaToCollection.mockReturnValue({
    mutateAsync: mocks.mutateAsync,
    isPending: false,
  });

  mocks.mutateAsync.mockResolvedValue(undefined);
});

describe("MangaDetail Page", () => {
  test("renders manga details", () => {
    renderMangaDetail();

    expect(
      screen.getByRole("heading", { name: /naruto/i })
    ).toBeInTheDocument();

    expect(screen.getByText(/a ninja story/i)).toBeInTheDocument();
    expect(screen.getByText(/published: 1999-09-21/i)).toBeInTheDocument();
    expect(screen.getByText(/avg: 4.2/i)).toBeInTheDocument();
    expect(screen.getByText(/external: 4.7/i)).toBeInTheDocument();

    expect(screen.getByText(/shounen/i)).toBeInTheDocument();
    expect(screen.getByText(/action/i)).toBeInTheDocument();
    expect(screen.getByText(/adventure/i)).toBeInTheDocument();

    expect(screen.getByAltText(/naruto/i)).toHaveAttribute(
      "src",
      "https://example.com/naruto.jpg"
    );
  });

  test("shows loading state", () => {
    mocks.useManga.mockReturnValue({
      data: undefined,
      isPending: true,
      isError: false,
    });

    renderMangaDetail();

    expect(screen.getByText(/loading manga/i)).toBeInTheDocument();
  });

  test("shows error state", () => {
    mocks.useManga.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
    });

    renderMangaDetail();

    expect(screen.getByText(/couldn't load this manga/i)).toBeInTheDocument();
  });

  test("shows invalid manga id state", () => {
    renderMangaDetail("/manga/not-a-number");

    expect(screen.getByText(/invalid manga id/i)).toBeInTheDocument();
  });

  test("uses search as the default back link", () => {
    renderMangaDetail();

    expect(screen.getByRole("link", { name: /back to results/i })).toHaveAttribute(
      "href",
      "/search"
    );
  });

  test("uses returnTo state for the back link", () => {
    renderMangaDetail({
      pathname: "/manga/10",
      state: {
        returnTo: "/recommendations?collectionId=1",
      },
    });

    expect(screen.getByRole("link", { name: /back to results/i })).toHaveAttribute(
      "href",
      "/recommendations?collectionId=1"
    );
  });

  test("does not show collection controls when unauthenticated", () => {
    renderMangaDetail();

    expect(
      screen.queryByDisplayValue(/add to collection/i)
    ).not.toBeInTheDocument();

    expect(screen.queryByRole("button", { name: /^add$/i })).not.toBeInTheDocument();
  });

  test("shows collection controls when authenticated", () => {
    mocks.useMe.mockReturnValue({
      data: { id: "user-1", email: "test@example.com" },
      isPending: false,
    });

    renderMangaDetail();

    expect(screen.getByDisplayValue(/add to collection/i)).toBeInTheDocument();
    expect(screen.getByText(/favorites/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^add$/i })).toBeDisabled();
  });

  test("adds manga to selected collection", async () => {
    mocks.useMe.mockReturnValue({
      data: { id: "user-1", email: "test@example.com" },
      isPending: false,
    });

    renderMangaDetail();

    fireEvent.change(screen.getByDisplayValue(/add to collection/i), {
      target: { value: "1" },
    });

    fireEvent.click(screen.getByRole("button", { name: /^add$/i }));

    await waitFor(() => {
      expect(mocks.mutateAsync).toHaveBeenCalledWith(10);
    });

    expect(
      await screen.findByText(/manga added to collection/i)
    ).toBeInTheDocument();
  });

  test("shows add-to-collection error feedback", async () => {
    mocks.useMe.mockReturnValue({
      data: { id: "user-1", email: "test@example.com" },
      isPending: false,
    });

    mocks.mutateAsync.mockRejectedValueOnce(new Error("Already in collection."));

    renderMangaDetail();

    fireEvent.change(screen.getByDisplayValue(/add to collection/i), {
      target: { value: "1" },
    });

    fireEvent.click(screen.getByRole("button", { name: /^add$/i }));

    expect(
      await screen.findByText(/already in collection/i)
    ).toBeInTheDocument();
  });

  test("shows empty collections message for authenticated user with no collections", () => {
    mocks.useMe.mockReturnValue({
      data: { id: "user-1", email: "test@example.com" },
      isPending: false,
    });

    mocks.useCollections.mockReturnValue({
      data: {
        total_results: 0,
        page: 1,
        size: 100,
        items: [],
      },
      isLoading: false,
    });

    renderMangaDetail();

    expect(
      screen.getByText(/you don't have any collections yet/i)
    ).toBeInTheDocument();
  });

  test("shows fallback description when manga has no description", () => {
    mocks.useManga.mockReturnValue({
      data: {
        ...mangaDetail,
        description: null,
      },
      isPending: false,
      isError: false,
    });

    renderMangaDetail();

    expect(screen.getByText(/no description available/i)).toBeInTheDocument();
  });
});