import { fireEvent, screen } from "@testing-library/react";
import { vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import MangaCard from "../../src/components/MangaCard";
import { renderWithProviders } from "../testUtils";

const mockToggle = vi.fn();

const manga = {
  manga_id: 10,
  title: "Naruto",
  cover_image_url: "https://example.com/naruto.jpg",
  external_average_rating: 4.8,
  recommendation_score: 11.2,
  genres: [],
};

function renderCard(props = {}) {
  return renderWithProviders(
    <MemoryRouter initialEntries={["/search?q=naruto"]}>
      <MangaCard manga={manga} {...props} />
    </MemoryRouter>,
    { withRouter: false }
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("MangaCard", () => {
  test("renders manga title and cover image", () => {
    renderCard();

    expect(
      screen.getByRole("heading", { name: /naruto/i })
    ).toBeInTheDocument();

    expect(screen.getByAltText(/naruto/i)).toHaveAttribute(
      "src",
      "https://example.com/naruto.jpg"
    );
  });

  test("links to manga detail page", () => {
    renderCard();

    expect(screen.getByRole("link", { name: /naruto/i })).toHaveAttribute(
      "href",
      "/manga/10"
    );
  });

  test("uses fallback cover when no cover image exists", () => {
    renderCard({
      manga: {
        ...manga,
        cover_image_url: null,
      },
    });

    expect(screen.getByAltText(/naruto/i)).toHaveAttribute(
      "src",
      "https://placehold.co/400x600?text=No+Cover"
    );
  });

  test("does not show select button when not selectable", () => {
    renderCard({
      onToggleSelect: mockToggle,
    });

    expect(
      screen.queryByRole("button", { name: /select naruto/i })
    ).not.toBeInTheDocument();
  });

  test("does not show select button without toggle handler", () => {
    renderCard({
      selectable: true,
    });

    expect(
      screen.queryByRole("button", { name: /select naruto/i })
    ).not.toBeInTheDocument();
  });

  test("shows select button when selectable", () => {
    renderCard({
      selectable: true,
      selected: false,
      onToggleSelect: mockToggle,
    });

    expect(
      screen.getByRole("button", { name: /select naruto/i })
    ).toBeInTheDocument();
  });

  test("calls toggle handler when select button is clicked", () => {
    renderCard({
      selectable: true,
      selected: false,
      onToggleSelect: mockToggle,
    });

    fireEvent.click(screen.getByRole("button", { name: /select naruto/i }));

    expect(mockToggle).toHaveBeenCalledTimes(1);
    expect(mockToggle).toHaveBeenCalledWith(manga);
  });

  test("shows deselect button when selected", () => {
    renderCard({
      selectable: true,
      selected: true,
      onToggleSelect: mockToggle,
    });

    expect(
      screen.getByRole("button", { name: /deselect naruto/i })
    ).toBeInTheDocument();
  });

  test("calls toggle handler when deselect button is clicked", () => {
    renderCard({
      selectable: true,
      selected: true,
      onToggleSelect: mockToggle,
    });

    fireEvent.click(screen.getByRole("button", { name: /deselect naruto/i }));

    expect(mockToggle).toHaveBeenCalledTimes(1);
    expect(mockToggle).toHaveBeenCalledWith(manga);
  });

  test("applies selected styling when selected", () => {
    renderCard({
      selected: true,
    });

    expect(screen.getByRole("link", { name: /naruto/i })).toHaveClass(
      "border-neutral-300"
    );
  });

  test("renders long titles", () => {
    renderCard({
      manga: {
        ...manga,
        title:
          "Naruto Shippuden Ultimate Ninja Storm Generations Collection Deluxe Edition",
      },
    });

    expect(
      screen.getByRole("heading", {
        name: /naruto shippuden ultimate ninja storm generations collection deluxe edition/i,
      })
    ).toBeInTheDocument();
  });
});