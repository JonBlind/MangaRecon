import { fireEvent, screen } from "@testing-library/react";
import { vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import AuthRequiredModal from "../../src/components/AuthRequiredModal";
import { renderWithProviders } from "../testUtils";

const onClose = vi.fn();

function renderModal(props = {}) {
  return renderWithProviders(
    <MemoryRouter>
      <AuthRequiredModal
        open={true}
        onClose={onClose}
        {...props}
      />
    </MemoryRouter>,
    { withRouter: false }
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("AuthRequiredModal", () => {
  test("does not render when closed", () => {
    renderModal({ open: false });

    expect(
      screen.queryByRole("heading", { name: /sign in required/i })
    ).not.toBeInTheDocument();
  });

  test("renders default title and message", () => {
    renderModal();

    expect(
      screen.getByRole("heading", { name: /sign in required/i })
    ).toBeInTheDocument();

    expect(
      screen.getByText(/you need an account to add manga to a collection/i)
    ).toBeInTheDocument();
  });

  test("renders custom title and message", () => {
    renderModal({
      title: "Authentication Required",
      message: "Please sign in to continue.",
    });

    expect(
      screen.getByRole("heading", { name: /authentication required/i })
    ).toBeInTheDocument();

    expect(
      screen.getByText(/please sign in to continue/i)
    ).toBeInTheDocument();
  });

  test("renders close button", () => {
    renderModal();

    expect(
      screen.getByRole("button", { name: /close/i })
    ).toBeInTheDocument();
  });

  test("renders create account link", () => {
    renderModal();

    expect(
      screen.getByRole("link", { name: /create account/i })
    ).toHaveAttribute("href", "/register");
  });

  test("renders sign in link", () => {
    renderModal();

    expect(
      screen.getByRole("link", { name: /sign in/i })
    ).toHaveAttribute("href", "/login");
  });

  test("calls onClose when close button is clicked", () => {
    renderModal();

    fireEvent.click(
      screen.getByRole("button", { name: /close/i })
    );

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test("calls onClose when create account link is clicked", () => {
    renderModal();

    fireEvent.click(
      screen.getByRole("link", { name: /create account/i })
    );

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test("calls onClose when sign in link is clicked", () => {
    renderModal();

    fireEvent.click(
      screen.getByRole("link", { name: /^sign in$/i })
    );

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test("calls onClose when backdrop is clicked", () => {
    renderModal();

    fireEvent.click(screen.getByRole("dialog").parentElement!);

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test("does not close when modal content is clicked", () => {
    renderModal();

    fireEvent.click(
      screen.getByRole("heading", { name: /sign in required/i })
    );

    expect(onClose).not.toHaveBeenCalled();
  });
});