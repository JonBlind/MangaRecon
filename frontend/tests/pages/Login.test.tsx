import { screen, fireEvent, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import { renderWithProviders } from "../testUtils";
import Login from "../../src/pages/Login";
import * as authApi from "../../src/api/auth";
import { ApiRequestError } from "../../src/api/http";

// Mock auth hook so page renders normally
vi.mock("../../src/hooks/useMe", () => ({
  useMe: () => ({
    data: null,
    isLoading: false,
  }),
}));

// Spy on login API
const loginMock = vi.spyOn(authApi, "login").mockResolvedValue({} as any);

beforeEach(() => {
  vi.clearAllMocks();
});

describe("Login Page", () => {
  test("renders login form", () => {
    renderWithProviders(<Login />);

    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
  });

  test("calls login on submit", async () => {
    renderWithProviders(<Login />);

    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: "test@example.com" },
    });

    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: "password123" },
    });

    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(loginMock).toHaveBeenCalledWith("test@example.com", "password123");
    });
  });

  test("shows error message when login fails", async () => {
    loginMock.mockRejectedValueOnce(new ApiRequestError("Invalid credentials", 401));

    renderWithProviders(<Login />);

    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: "bad@example.com" },
    });

    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: "wrongpassword" },
    });

    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText(/invalid credentials/i)).toBeInTheDocument();
  });

  test("offers to resend verification when an unverified user logs in", async () => {
    loginMock.mockRejectedValueOnce(
      new ApiRequestError(
        "Please verify your email before logging in.",
        403,
        "AUTH_NOT_VERIFIED",
      ),
    );

    renderWithProviders(<Login />);

    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: "unverified@example.com" },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: "password123" },
    });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText(/please verify your email/i)).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /resend verification email/i }),
    ).toHaveAttribute("href", "/verify-email");
  });
});
