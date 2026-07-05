import { fireEvent, screen } from "@testing-library/react";
import { vi } from "vitest";
import SearchSelectionBar from "../../src/components/SearchSelectionBar";
import { renderWithProviders } from "../testUtils";

const onClear = vi.fn();
const onGetRecommendations = vi.fn();
const onAddToCollection = vi.fn();

function renderBar(props = {}) {
  return renderWithProviders(
    <SearchSelectionBar
      selectedCount={2}
      onClear={onClear}
      onGetRecommendations={onGetRecommendations}
      onAddToCollection={onAddToCollection}
      {...props}
    />
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("SearchSelectionBar", () => {
  test("renders selected count and action buttons", () => {
    renderBar();

    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText(/selected/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /clear/i })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /add to collection/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /get recommendations/i })
    ).toBeInTheDocument();
  });

  test("does not render when selected count is zero", () => {
    renderBar({ selectedCount: 0 });

    expect(screen.queryByText(/selected/i)).not.toBeInTheDocument();
  });

  test("does not render when selected count is negative", () => {
    renderBar({ selectedCount: -1 });

    expect(screen.queryByText(/selected/i)).not.toBeInTheDocument();
  });

  test("calls clear handler", () => {
    renderBar();

    fireEvent.click(screen.getByRole("button", { name: /clear/i }));

    expect(onClear).toHaveBeenCalledTimes(1);
  });

  test("calls get recommendations handler", () => {
    renderBar();

    fireEvent.click(
      screen.getByRole("button", { name: /get recommendations/i })
    );

    expect(onGetRecommendations).toHaveBeenCalledTimes(1);
  });

  test("calls add to collection handler when user can add", () => {
    renderBar({ canAddToCollection: true });

    fireEvent.click(screen.getByRole("button", { name: /add to collection/i }));

    expect(onAddToCollection).toHaveBeenCalledTimes(1);
  });

  test("shows sign in button when user cannot add to collection", () => {
    renderBar({ canAddToCollection: false });

    expect(
      screen.getByRole("button", { name: /sign in to save/i })
    ).toBeInTheDocument();

    expect(screen.queryByRole("button", { name: /add to collection/i }))
      .not.toBeInTheDocument();
  });

  test("calls add handler from sign in button", () => {
    renderBar({ canAddToCollection: false });

    fireEvent.click(screen.getByRole("button", { name: /sign in to save/i }));

    expect(onAddToCollection).toHaveBeenCalledTimes(1);
  });

  test("uses authenticated add title when user can add", () => {
    renderBar({ canAddToCollection: true });

    expect(screen.getByRole("button", { name: /add to collection/i }))
      .toHaveAttribute("title", "Add selected manga to a collection");
  });

  test("uses sign in title when user cannot add", () => {
    renderBar({ canAddToCollection: false });

    expect(screen.getByRole("button", { name: /sign in to save/i }))
      .toHaveAttribute("title", "Sign in to save manga to a collection");
  });
});