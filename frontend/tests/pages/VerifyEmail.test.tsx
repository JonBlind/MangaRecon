import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, test, vi } from "vitest";

import { ApiRequestError } from "../../src/api/http";
import VerifyEmail from "../../src/pages/VerifyEmail";

const mocks = vi.hoisted(() => ({
  requestVerificationEmail: vi.fn(),
  verifyEmail: vi.fn(),
}));

vi.mock("../../src/api/auth", () => ({
  requestVerificationEmail: mocks.requestVerificationEmail,
  verifyEmail: mocks.verifyEmail,
}));

function renderVerifyEmail(initialEntry = "/verify-email") {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/verify-email" element={<VerifyEmail />} />
          <Route path="/login" element={<div>Login page</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.verifyEmail.mockResolvedValue({});
  mocks.requestVerificationEmail.mockResolvedValue({});
});

describe("VerifyEmail Page", () => {
  test("verifies the token from the email link", async () => {
    renderVerifyEmail("/verify-email?token=verification-token");

    expect(screen.getByText(/verifying your email/i)).toBeInTheDocument();

    expect(
      await screen.findByRole("heading", { name: /email verified/i }),
    ).toBeInTheDocument();
    expect(mocks.verifyEmail).toHaveBeenCalledTimes(1);
    expect(mocks.verifyEmail).toHaveBeenCalledWith("verification-token");
    expect(screen.getByRole("link", { name: /continue to login/i })).toHaveAttribute(
      "href",
      "/login",
    );
  });

  test("shows an expired-link state when verification fails", async () => {
    mocks.verifyEmail.mockRejectedValueOnce(
      new ApiRequestError(
        "This verification link is invalid or expired.",
        400,
        "AUTH_VERIFY_INVALID",
      ),
    );

    renderVerifyEmail("/verify-email?token=expired-token");

    expect(
      await screen.findByRole("heading", {
        name: /verification link failed/i,
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/verification link is invalid or expired/i),
    ).toBeInTheDocument();
  });

  test("treats an already-used token as a completed verification", async () => {
    mocks.verifyEmail.mockRejectedValueOnce(
      new ApiRequestError(
        "This email address is already verified.",
        409,
        "AUTH_ALREADY_VERIFIED",
      ),
    );

    renderVerifyEmail("/verify-email?token=already-used-token");

    expect(
      await screen.findByRole("heading", { name: /email verified/i }),
    ).toBeInTheDocument();
  });

  test("resends a verification email without revealing account existence", async () => {
    renderVerifyEmail();

    fireEvent.change(screen.getByLabelText(/^email$/i), {
      target: { value: "reader@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: /resend verification email/i }));

    await waitFor(() => {
      expect(mocks.requestVerificationEmail).toHaveBeenCalledWith("reader@example.com");
    });
    expect(
      screen.getByText(/if that address belongs to an unverified account/i),
    ).toBeInTheDocument();
  });
});
