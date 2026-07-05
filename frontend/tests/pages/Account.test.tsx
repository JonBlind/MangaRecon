import { fireEvent, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import Account from "../../src/pages/Account";
import { renderWithProviders } from "../testUtils";

const mocks = vi.hoisted(() => ({
  useMe: vi.fn(),
  useUpdateProfile: vi.fn(),
  mutateAsync: vi.fn(),
}));

vi.mock("../../src/hooks/useMe", () => ({
  useMe: () => mocks.useMe(),
}));

vi.mock("../../src/hooks/useProfile", () => ({
  useUpdateProfile: () => mocks.useUpdateProfile(),
}));

const user = {
  id: "user-1",
  email: "test@example.com",
  username: "testuser",
  displayname: "Test User",
};

beforeEach(() => {
  vi.clearAllMocks();

  mocks.useMe.mockReturnValue({
    data: user,
    isLoading: false,
  });

  mocks.useUpdateProfile.mockReturnValue({
    mutateAsync: mocks.mutateAsync,
    isPending: false,
    isSuccess: false,
    error: null,
  });

  mocks.mutateAsync.mockResolvedValue(undefined);
});

describe("Account Page", () => {
  test("renders account information", () => {
    renderWithProviders(<Account />);

    expect(
      screen.getByRole("heading", { name: /account/i })
    ).toBeInTheDocument();

    expect(screen.getByText(/username:/i)).toBeInTheDocument();
    expect(screen.getByText(/testuser/i)).toBeInTheDocument();

    expect(screen.getByText(/email:/i)).toBeInTheDocument();
    expect(screen.getByText(/test@example.com/i)).toBeInTheDocument();

    expect(screen.getByLabelText(/display name/i)).toHaveValue("Test User");
  });

  test("shows loading state", () => {
    mocks.useMe.mockReturnValue({
      data: undefined,
      isLoading: true,
    });

    renderWithProviders(<Account />);

    expect(screen.getByText(/loading account/i)).toBeInTheDocument();
  });

  test("shows not authenticated state", () => {
    mocks.useMe.mockReturnValue({
      data: null,
      isLoading: false,
    });

    renderWithProviders(<Account />);

    expect(screen.getByText(/not authenticated/i)).toBeInTheDocument();
  });

  test("disables save button when display name is unchanged", () => {
    renderWithProviders(<Account />);

    expect(screen.getByRole("button", { name: /save/i })).toBeDisabled();
  });

  test("enables save button when display name changes", () => {
    renderWithProviders(<Account />);

    fireEvent.change(screen.getByLabelText(/display name/i), {
      target: { value: "Updated User" },
    });

    expect(screen.getByRole("button", { name: /save/i })).toBeEnabled();
  });

  test("submits updated display name", async () => {
    renderWithProviders(<Account />);

    fireEvent.change(screen.getByLabelText(/display name/i), {
      target: { value: "Updated User" },
    });

    fireEvent.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => {
      expect(mocks.mutateAsync).toHaveBeenCalledWith({
        displayname: "Updated User",
      });
    });
  });

  test("trims display name before submitting", async () => {
    renderWithProviders(<Account />);

    fireEvent.change(screen.getByLabelText(/display name/i), {
      target: { value: "   Updated User   " },
    });

    fireEvent.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => {
      expect(mocks.mutateAsync).toHaveBeenCalledWith({
        displayname: "Updated User",
      });
    });
  });

  test("does not allow saving an empty display name", () => {
    renderWithProviders(<Account />);

    fireEvent.change(screen.getByLabelText(/display name/i), {
      target: { value: "   " },
    });

    expect(screen.getByRole("button", { name: /save/i })).toBeDisabled();
  });

  test("shows saving state", () => {
    mocks.useUpdateProfile.mockReturnValue({
      mutateAsync: mocks.mutateAsync,
      isPending: true,
      isSuccess: false,
      error: null,
    });

    renderWithProviders(<Account />);

    expect(screen.getByRole("button", { name: /saving/i })).toBeDisabled();
  });

  test("shows success message after profile update", () => {
    mocks.useUpdateProfile.mockReturnValue({
      mutateAsync: mocks.mutateAsync,
      isPending: false,
      isSuccess: true,
      error: null,
    });

    renderWithProviders(<Account />);

    expect(screen.getByText(/profile updated/i)).toBeInTheDocument();
  });

  test("shows generic error message when update fails", () => {
    mocks.useUpdateProfile.mockReturnValue({
      mutateAsync: mocks.mutateAsync,
      isPending: false,
      isSuccess: false,
      error: new Error("Something failed"),
    });

    renderWithProviders(<Account />);

    expect(screen.getByText(/failed to update profile/i)).toBeInTheDocument();
  });
});