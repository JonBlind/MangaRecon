import { fireEvent, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import Register from "../../src/pages/Register";
import { renderWithProviders } from "../testUtils";
import * as authApi from "../../src/api/auth";

vi.mock("../../src/hooks/useMe", () => ({
  useMe: () => ({
    data: null,
    isLoading: false,
  }),
}));

beforeEach(() => {
  vi.clearAllMocks();
});

const registerMock = vi
  .spyOn(authApi, "register")
  .mockResolvedValue({} as any);

describe("Register Page", () => {
  test("renders register form", () => {
    renderWithProviders(<Register />);

    expect(
      screen.getByRole("button", { name: /create account/i })
    ).toBeInTheDocument();
  });

  test("calls register on submit", async () => {
    renderWithProviders(<Register />);

    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: "test@example.com" },
    });

    fireEvent.change(screen.getByLabelText(/username/i), {
      target: { value: "testuser" },
    });

    fireEvent.change(screen.getByLabelText(/display name/i), {
      target: { value: "Test User" },
    });

    fireEvent.change(screen.getByLabelText(/^password/i), {
      target: { value: "password123" },
    });

    fireEvent.change(screen.getByLabelText(/confirm password/i), {
      target: { value: "password123" },
    });

    fireEvent.click(
      screen.getByRole("button", { name: /create account/i })
    );

    await waitFor(() => {
      expect(registerMock).toHaveBeenCalledWith({
        email: "test@example.com",
        username: "testuser",
        displayname: "Test User",
        password: "password123",
      });
    });
  });

  test("shows error when passwords do not match", async () => {
    renderWithProviders(<Register />);

    fireEvent.change(screen.getByLabelText(/email/i), {
        target: { value: "test@example.com" },
    });

    fireEvent.change(screen.getByLabelText(/username/i), {
        target: { value: "testuser" },
    });

    fireEvent.change(screen.getByLabelText(/display name/i), {
        target: { value: "Test User" },
    });

    fireEvent.change(screen.getByLabelText(/^password/i), {
        target: { value: "password123" },
    });

    fireEvent.change(screen.getByLabelText(/confirm password/i), {
        target: { value: "different123" },
    });

    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    expect(
        await screen.findByText(/passwords do not match/i)
    ).toBeInTheDocument();

    expect(registerMock).not.toHaveBeenCalled();
  });

  test("shows friendly error when account already exists", async () => {
    registerMock.mockRejectedValueOnce(
        new Error("REGISTER_USER_ALREADY_EXISTS")
    );

    renderWithProviders(<Register />);

    fireEvent.change(screen.getByLabelText(/email/i), {
        target: { value: "test@example.com" },
    });

    fireEvent.change(screen.getByLabelText(/username/i), {
        target: { value: "testuser" },
    });

    fireEvent.change(screen.getByLabelText(/display name/i), {
        target: { value: "Test User" },
    });

    fireEvent.change(screen.getByLabelText(/^password/i), {
        target: { value: "password123" },
    });

    fireEvent.change(screen.getByLabelText(/confirm password/i), {
        target: { value: "password123" },
    });

    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    expect(
        await screen.findByText(/an account with that email already exists/i)
    ).toBeInTheDocument();
  });
});