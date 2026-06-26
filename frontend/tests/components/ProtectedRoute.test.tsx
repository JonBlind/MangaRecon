import { screen } from "@testing-library/react";
import { vi } from "vitest";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import ProtectedRoute from "../../src/components/ProtectedRoute";
import { renderWithProviders } from "../testUtils";

const mockUseMe = vi.fn();

vi.mock("../../src/hooks/useMe", () => ({
  useMe: () => mockUseMe(),
}));

function renderProtectedRoute() {
  return renderWithProviders(
    <MemoryRouter initialEntries={["/collections"]}>
      <Routes>
        <Route element={<ProtectedRoute />}>
          <Route path="/collections" element={<div>Collections Page</div>} />
        </Route>

        <Route path="/login" element={<div>Login Page</div>} />
      </Routes>
    </MemoryRouter>,
    { withRouter: false }
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ProtectedRoute", () => {
  test("shows loading state while auth is pending", () => {
    mockUseMe.mockReturnValue({
      data: undefined,
      isPending: true,
      isFetching: false,
      isError: false,
    });

    renderProtectedRoute();

    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  test("redirects unauthenticated user to login", () => {
    mockUseMe.mockReturnValue({
      data: null,
      isPending: false,
      isFetching: false,
      isError: false,
    });

    renderProtectedRoute();

    expect(screen.getByText(/login page/i)).toBeInTheDocument();
  });

  test("renders protected content when authenticated", () => {
    mockUseMe.mockReturnValue({
      data: {
        id: "user-1",
        email: "test@example.com",
        username: "testuser",
        displayname: "Test User",
      },
      isPending: false,
      isFetching: false,
      isError: false,
    });

    renderProtectedRoute();

    expect(screen.getByText(/collections page/i)).toBeInTheDocument();
  });
});