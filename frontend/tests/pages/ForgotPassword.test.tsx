import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";

import ForgotPassword from "../../src/pages/ForgotPassword";
import { ApiRequestError } from "../../src/api/http";
import { renderWithProviders } from "../testUtils";

const mocks = vi.hoisted(() => ({
  requestPasswordReset: vi.fn(),
}));

vi.mock("../../src/api/auth", () => ({
  requestPasswordReset: mocks.requestPasswordReset,
}));

beforeEach(() => {
  vi.clearAllMocks();
  mocks.requestPasswordReset.mockResolvedValue({});
});

describe("ForgotPassword Page", () => {
  test("submits a normalized email and shows a generic response", async () => {
    renderWithProviders(<ForgotPassword />);

    fireEvent.change(screen.getByLabelText(/^email$/i), {
      target: { value: "  reader@example.com  " },
    });
    fireEvent.click(screen.getByRole("button", { name: /send reset link/i }));

    await waitFor(() => {
      expect(mocks.requestPasswordReset).toHaveBeenCalledWith("reader@example.com");
    });
    expect(
      screen.getByText(/if that address belongs to an account/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /back to login/i })).toHaveAttribute(
      "href",
      "/login",
    );
  });

  test("shows a retryable error when the request fails", async () => {
    mocks.requestPasswordReset.mockRejectedValueOnce(new Error("network"));
    renderWithProviders(<ForgotPassword />);

    fireEvent.change(screen.getByLabelText(/^email$/i), {
      target: { value: "reader@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: /send reset link/i }));

    expect(await screen.findByText(/could not submit your request/i)).toBeInTheDocument();
  });

  test("explains when too many reset requests were submitted", async () => {
    mocks.requestPasswordReset.mockRejectedValueOnce(
      new ApiRequestError("Rate limit exceeded", 429, "RATE_LIMIT_EXCEEDED"),
    );
    renderWithProviders(<ForgotPassword />);

    fireEvent.change(screen.getByLabelText(/^email$/i), {
      target: { value: "reader@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: /send reset link/i }));

    expect(await screen.findByText(/too many reset requests/i)).toBeInTheDocument();
  });
});
