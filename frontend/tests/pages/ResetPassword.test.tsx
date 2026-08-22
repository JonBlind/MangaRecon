import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, test, vi } from "vitest";

import { ApiRequestError } from "../../src/api/http";
import ResetPassword from "../../src/pages/ResetPassword";

const mocks = vi.hoisted(() => ({
  resetPassword: vi.fn(),
  validatePasswordResetToken: vi.fn(),
}));

vi.mock("../../src/api/auth", () => ({
  resetPassword: mocks.resetPassword,
  validatePasswordResetToken: mocks.validatePasswordResetToken,
}));

function renderResetPassword(initialEntry = "/reset-password?token=reset-token") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/forgot-password" element={<div>Forgot password</div>} />
        <Route path="/login" element={<div>Login page</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.validatePasswordResetToken.mockResolvedValue({});
  mocks.resetPassword.mockResolvedValue({});
});

describe("ResetPassword Page", () => {
  test("validates the token before rendering the password form", async () => {
    renderResetPassword();

    expect(screen.getByText(/checking your reset link/i)).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: /choose a new password/i }),
    ).toBeInTheDocument();
    expect(mocks.validatePasswordResetToken).toHaveBeenCalledWith("reset-token");
  });

  test("submits matching passwords and shows success", async () => {
    renderResetPassword();
    await screen.findByRole("heading", { name: /choose a new password/i });

    fireEvent.change(screen.getByLabelText(/^new password$/i), {
      target: { value: "newpassword123" },
    });
    fireEvent.change(screen.getByLabelText(/^confirm password$/i), {
      target: { value: "newpassword123" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^reset password$/i }));

    await waitFor(() => {
      expect(mocks.resetPassword).toHaveBeenCalledWith("reset-token", "newpassword123");
    });
    expect(
      await screen.findByRole("heading", { name: /^password reset$/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /continue to login/i })).toHaveAttribute(
      "href",
      "/login",
    );
  });

  test("rejects mismatched passwords without calling the API", async () => {
    renderResetPassword();
    await screen.findByRole("heading", { name: /choose a new password/i });

    fireEvent.change(screen.getByLabelText(/^new password$/i), {
      target: { value: "newpassword123" },
    });
    fireEvent.change(screen.getByLabelText(/^confirm password$/i), {
      target: { value: "different123" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^reset password$/i }));

    expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument();
    expect(mocks.resetPassword).not.toHaveBeenCalled();
  });

  test("shows an invalid state when token validation fails", async () => {
    mocks.validatePasswordResetToken.mockRejectedValueOnce(
      new ApiRequestError("Bad token", 400, "AUTH_RESET_INVALID"),
    );

    renderResetPassword("/reset-password?token=expired-token");

    expect(
      await screen.findByRole("heading", { name: /reset link unavailable/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/invalid, expired, or has already been used/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /request a new link/i })).toHaveAttribute(
      "href",
      "/forgot-password",
    );
  });

  test("shows a retry state when token validation is rate limited", async () => {
    mocks.validatePasswordResetToken.mockRejectedValueOnce(
      new ApiRequestError("Rate limit exceeded", 429, "RATE_LIMIT_EXCEEDED"),
    );

    renderResetPassword("/reset-password?token=limited-token");

    expect(
      await screen.findByRole("heading", { name: /too many reset attempts/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/please wait a minute/i)).toBeInTheDocument();
  });

  test("does not call validation when the token is missing", () => {
    renderResetPassword("/reset-password");

    expect(
      screen.getByRole("heading", { name: /reset link unavailable/i }),
    ).toBeInTheDocument();
    expect(mocks.validatePasswordResetToken).not.toHaveBeenCalled();
  });
});
