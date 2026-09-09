import { screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { vi } from "vitest";
import Layout from "../../src/components/Layout";
import { renderWithProviders } from "../testUtils";

const mocks = vi.hoisted(() => ({
  useMe: vi.fn(),
  logout: vi.fn(),
}));

vi.mock("../../src/hooks/useMe", () => ({
  useMe: (enabled = true) => mocks.useMe(enabled),
}));

vi.mock("../../src/api/auth", () => ({
  logout: mocks.logout,
}));

function renderLayout(pathname: string) {
  return renderWithProviders(
    <MemoryRouter initialEntries={[pathname]}>
      <Routes>
        <Route element={<Layout />}>
          <Route path="*" element={<div>Current page</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
    { withRouter: false },
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.useMe.mockReturnValue({
    data: null,
    isLoading: false,
    isPending: false,
  });
});

describe("Layout auth request priority", () => {
  test.each(["/search", "/search/", "/manga/10"])(
    "lets the public page request load first at %s",
    (pathname) => {
      renderLayout(pathname);

      expect(screen.getByText("Current page")).toBeInTheDocument();
      expect(mocks.useMe).toHaveBeenLastCalledWith(false);
    },
  );

  test("loads auth immediately on a page without a primary public request", () => {
    renderLayout("/");

    expect(mocks.useMe).toHaveBeenLastCalledWith(true);
  });
});
