import { fireEvent, render, screen } from "@testing-library/react";
import { Link, MemoryRouter, Route, Routes } from "react-router-dom";
import SearchMetadata from "../../src/components/SearchMetadata";

function MetadataTestPage() {
  return (
    <>
      <Link to="/">Landing</Link>
      <Link to="/search">Search</Link>
    </>
  );
}

function renderMetadata(pathname: string) {
  return render(
    <MemoryRouter initialEntries={[pathname]}>
      <Routes>
        <Route element={<SearchMetadata />}>
          <Route path="*" element={<MetadataTestPage />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  document.title = "";
  document.head.querySelector('meta[name="robots"]')?.remove();
  document.head.querySelector('link[rel="canonical"]')?.remove();
});

describe("SearchMetadata", () => {
  test("marks the landing page as indexable and canonical", () => {
    renderMetadata("/");

    expect(document.title).toBe("MangaRecon — Discover and Organize Manga");
    expect(document.head.querySelector('meta[name="robots"]')).toHaveAttribute(
      "content",
      "index, follow",
    );
    expect(document.head.querySelector('link[rel="canonical"]')).toHaveAttribute(
      "href",
      "https://mangarecon.com/",
    );
  });

  test("marks application routes as non-indexable", () => {
    renderMetadata("/search");

    expect(document.title).toBe("MangaRecon");
    expect(document.head.querySelector('meta[name="robots"]')).toHaveAttribute(
      "content",
      "noindex, follow",
    );
    expect(document.head.querySelector('link[rel="canonical"]')).not.toBeInTheDocument();
  });

  test("updates metadata during client-side navigation", () => {
    renderMetadata("/");

    fireEvent.click(screen.getByRole("link", { name: "Search" }));

    expect(document.head.querySelector('meta[name="robots"]')).toHaveAttribute(
      "content",
      "noindex, follow",
    );
    expect(document.head.querySelector('link[rel="canonical"]')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("link", { name: "Landing" }));

    expect(document.head.querySelector('meta[name="robots"]')).toHaveAttribute(
      "content",
      "index, follow",
    );
    expect(document.head.querySelector('link[rel="canonical"]')).toHaveAttribute(
      "href",
      "https://mangarecon.com/",
    );
  });
});
