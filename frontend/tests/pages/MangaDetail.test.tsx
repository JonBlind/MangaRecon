import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import MangaDetail from "../../src/pages/MangaDetail";
import { renderWithProviders } from "../testUtils";

const mocks = vi.hoisted(() => ({
  useManga: vi.fn(),
  useMe: vi.fn(),
  useCollections: vi.fn(),
  useAddMangaToCollection: vi.fn(),
  useRating: vi.fn(),
  useSaveRating: vi.fn(),
  useDeleteRating: vi.fn(),

  mutateAsync: vi.fn(),
  saveRating: vi.fn(),
  deleteRating: vi.fn(),
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

vi.mock("../../src/hooks/useRatings", () => ({
  useRating: (mangaId: number, enabled: boolean) => mocks.useRating(mangaId, enabled),
  useSaveRating: (mangaId: number) => mocks.useSaveRating(mangaId),
  useDeleteRating: (mangaId: number) => mocks.useDeleteRating(mangaId),
}));

const mangaDetail = {
  manga_id: 10,
  title: "Naruto",
  description: "A ninja story.",
  published_date: "1999-09-21",
  average_rating: 8.4,
  external_average_rating: 8.7,
  creator_credits: [
    {
      creator_id: 1,
      creator_name: "Masashi Kishimoto",
      role: "author",
    },
  ],
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
      } = "/manga/10",
) {
  return renderWithProviders(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/manga/:id" element={<MangaDetail />} />
      </Routes>
    </MemoryRouter>,
    { withRouter: false },
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

  mocks.useRating.mockReturnValue({
    data: null,
    isPending: false,
    isError: false,
    isSuccess: true,
  });

  mocks.useSaveRating.mockReturnValue({
    mutateAsync: mocks.saveRating,
    isPending: false,
  });

  mocks.useDeleteRating.mockReturnValue({
    mutateAsync: mocks.deleteRating,
    isPending: false,
  });

  mocks.mutateAsync.mockResolvedValue(undefined);
  mocks.saveRating.mockResolvedValue(undefined);
  mocks.deleteRating.mockResolvedValue(undefined);
});

describe("MangaDetail Page", () => {
  test("renders manga details", () => {
    renderMangaDetail();

    const title = screen.getByRole("heading", { name: /naruto/i });
    const descriptionRegion = screen.getByRole("region", {
      name: /^description$/i,
    });

    expect(title).toBeInTheDocument();
    expect(title.parentElement).toContainElement(descriptionRegion);

    expect(
      within(descriptionRegion).getByText(/a ninja story/i),
    ).toBeInTheDocument();

    expect(screen.getByText(/published: 1999-09-21/i)).toBeInTheDocument();
    expect(screen.getByText(/user avg: 4.2 \/ 5/i)).toBeInTheDocument();
    expect(screen.getByText(/external: 8.7 \/ 10/i)).toBeInTheDocument();

    expect(screen.getByText(/shounen/i)).toBeInTheDocument();
    expect(screen.getByText(/action/i)).toBeInTheDocument();
    expect(screen.getByText(/adventure/i)).toBeInTheDocument();

    expect(screen.getByAltText(/naruto/i)).toHaveAttribute(
      "src",
      "https://example.com/naruto.jpg",
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
      "/search",
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
      "/recommendations?collectionId=1",
    );
  });

  test("does not show collection controls when unauthenticated", () => {
    renderMangaDetail();

    expect(screen.queryByDisplayValue(/add to collection/i)).not.toBeInTheDocument();

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
    expect(screen.getByRole("group", { name: /^your rating$/i })).toBeInTheDocument();
    expect(screen.getAllByRole("radio")).toHaveLength(10);
    expect(
      screen.queryByRole("button", { name: /save rating/i }),
    ).not.toBeInTheDocument();
  });

  test("loads and displays an existing personal rating", async () => {
    mocks.useMe.mockReturnValue({
      data: { id: "user-1", email: "test@example.com" },
      isPending: false,
    });
    mocks.useRating.mockReturnValue({
      data: {
        manga_id: 10,
        personal_rating: 9,
        created_at: "2026-08-09T00:00:00Z",
      },
      isPending: false,
      isError: false,
      isSuccess: true,
    });

    renderMangaDetail();

    await waitFor(() => {
      expect(screen.getByRole("radio", { name: /4.5 out of 5 stars/i })).toBeChecked();
    });
    expect(screen.getByRole("button", { name: /remove rating/i })).toBeInTheDocument();
  });

  test("saves a half-star selection immediately", async () => {
    mocks.useMe.mockReturnValue({
      data: { id: "user-1", email: "test@example.com" },
      isPending: false,
    });

    renderMangaDetail();

    fireEvent.click(screen.getByRole("radio", { name: /4.5 out of 5 stars/i }));

    await waitFor(() => {
      expect(mocks.saveRating).toHaveBeenCalledWith(9);
    });
    expect(screen.getByRole("radio", { name: /4.5 out of 5 stars/i })).toBeChecked();
    expect(await screen.findByText(/your rating was saved/i)).toBeInTheDocument();
  });

  test("removes an existing personal rating", async () => {
    mocks.useMe.mockReturnValue({
      data: { id: "user-1", email: "test@example.com" },
      isPending: false,
    });
    mocks.useRating.mockReturnValue({
      data: {
        manga_id: 10,
        personal_rating: 8,
        created_at: "2026-08-09T00:00:00Z",
      },
      isPending: false,
      isError: false,
      isSuccess: true,
    });

    renderMangaDetail();

    fireEvent.click(await screen.findByRole("button", { name: /remove rating/i }));

    await waitFor(() => {
      expect(mocks.deleteRating).toHaveBeenCalledWith();
    });
    expect(await screen.findByText(/your rating was removed/i)).toBeInTheDocument();
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

    expect(await screen.findByText(/manga added to collection/i)).toBeInTheDocument();
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

    expect(await screen.findByText(/already in collection/i)).toBeInTheDocument();
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

    expect(screen.getByText(/you don't have any collections yet/i)).toBeInTheDocument();
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

  test("renders demographics, genres, and tags in separate groups", () => {
    renderMangaDetail();

    const demographicsRegion = screen.getByRole("region", {
      name: /^demographics$/i,
    });
    const genresRegion = screen.getByRole("region", {
      name: /^genres$/i,
    });
    const tagsRegion = screen.getByRole("region", {
      name: /^tags$/i,
    });

    expect(
      within(demographicsRegion).getByText("Shounen"),
    ).toBeInTheDocument();

    expect(within(genresRegion).getByText("Action")).toBeInTheDocument();
    expect(
      within(genresRegion).queryByText("Adventure"),
    ).not.toBeInTheDocument();

    expect(within(tagsRegion).getByText("Adventure")).toBeInTheDocument();
    expect(within(tagsRegion).queryByText("Action")).not.toBeInTheDocument();
  });

  test("collapses and expands a long tag list", () => {
    const manyTags = Array.from({ length: 14 }, (_, index) => ({
      tag_id: index + 1,
      tag_name: `Tag ${index + 1}`,
    }));

    mocks.useManga.mockReturnValue({
      data: {
        ...mangaDetail,
        tags: manyTags,
      },
      isPending: false,
      isError: false,
    });

    renderMangaDetail();

    const tagsRegion = screen.getByRole("region", {
      name: /^tags$/i,
    });

    expect(within(tagsRegion).getByText("Tag 12")).toBeInTheDocument();
    expect(within(tagsRegion).queryByText("Tag 13")).not.toBeInTheDocument();

    fireEvent.click(
      within(tagsRegion).getByRole("button", {
        name: /show all 14 tags/i,
      }),
    );

    expect(within(tagsRegion).getByText("Tag 13")).toBeInTheDocument();
    expect(within(tagsRegion).getByText("Tag 14")).toBeInTheDocument();

    expect(
      within(tagsRegion).getByRole("button", {
        name: /show fewer tags/i,
      }),
    ).toHaveAttribute("aria-expanded", "true");

    fireEvent.click(
      within(tagsRegion).getByRole("button", {
        name: /show fewer tags/i,
      }),
    );

    expect(within(tagsRegion).queryByText("Tag 13")).not.toBeInTheDocument();
  });

  test("uses centered half-star hit zones and renders an exact half fill", () => {
    mocks.useMe.mockReturnValue({
      data: { id: "user-1", email: "test@example.com" },
      isPending: false,
    });

    const { container } = renderMangaDetail();

    const halfRadio = screen.getByRole("radio", {
      name: /0\.5 out of 5 stars/i,
    });
    const fullRadio = screen.getByRole("radio", {
      name: /1\.0 out of 5 stars/i,
    });

    expect(halfRadio.parentElement).toHaveClass("left-1/4", "w-1/2");
    expect(fullRadio.parentElement).toHaveClass("right-0", "w-1/4");

    const filledStarLayers = container.querySelectorAll<HTMLSpanElement>(
      'span[aria-hidden="true"][style]',
    );

    const halfLabel = container.querySelector<HTMLLabelElement>(
      `label[for="${halfRadio.id}"]`,
    );

    expect(filledStarLayers).toHaveLength(5);
    expect(halfLabel).not.toBeNull();

    fireEvent.mouseEnter(halfLabel!);

    expect(filledStarLayers[0]).toHaveStyle("width: 50%");
    expect(filledStarLayers[1]).toHaveStyle("width: 0%");

    const fullLabels = container.querySelectorAll<HTMLLabelElement>(
      `label[for="${fullRadio.id}"]`,
    );

    const previousRatingZone = Array.from(fullLabels).find((label) =>
      label.classList.contains("left-0"),
    );

    expect(previousRatingZone).toHaveClass("left-0", "w-1/4");

    fireEvent.mouseEnter(previousRatingZone!);

    expect(filledStarLayers[0]).toHaveStyle("width: 100%");
    expect(filledStarLayers[1]).toHaveStyle("width: 0%");
  });
});
