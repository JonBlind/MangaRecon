import { fireEvent, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import Account from "../../src/pages/Account";
import { renderWithProviders } from "../testUtils";

const DAY_MS = 24 * 60 * 60 * 1000;

const mocks = vi.hoisted(() => ({
  useMe: vi.fn(),
  useUpdateProfile: vi.fn(),
  mutateAsync: vi.fn(),
  reset: vi.fn(),
}));

vi.mock("../../src/hooks/useMe", () => ({
  useMe: () => mocks.useMe(),
}));

vi.mock("../../src/hooks/useProfile", () => ({
  useUpdateProfile: () =>
    mocks.useUpdateProfile(),
}));

const user = {
  id: "user-1",
  email: "test@example.com",
  username: "testuser",
  displayname: "Test User",
  username_changed_at: null,
  show_adult_content: false,
};

beforeEach(() => {
  vi.clearAllMocks();

  mocks.useMe.mockReturnValue({
    data: user,
    isLoading: false,
  });

  mocks.useUpdateProfile.mockReturnValue({
    mutateAsync: mocks.mutateAsync,
    reset: mocks.reset,
    isPending: false,
    isSuccess: false,
    error: null,
  });

  mocks.mutateAsync.mockResolvedValue(
    undefined,
  );
});

describe("Account Page", () => {
  test("renders account information", () => {
    renderWithProviders(<Account />);

    expect(
      screen.getByRole("heading", {
        name: "Account",
        level: 1,
      })
    ).toBeInTheDocument();

    expect(screen.getByText("testuser")).toBeInTheDocument();
    
    expect(screen.getByText(/test@example\.com/i)).toBeInTheDocument();

    expect(screen.getByLabelText(/display name/i)).toHaveValue("Test User");

    expect(screen.getByRole("button", {name: /change username/i})).toBeEnabled();
  });

  test("shows loading state", () => {
    mocks.useMe.mockReturnValue({
      data: undefined,
      isLoading: true,
    });

    renderWithProviders(<Account />);

    expect(
      screen.getByText(/loading account/i),
    ).toBeInTheDocument();
  });

  test("shows not authenticated state", () => {
    mocks.useMe.mockReturnValue({
      data: null,
      isLoading: false,
    });

    renderWithProviders(<Account />);

    expect(
      screen.getByText(/not authenticated/i),
    ).toBeInTheDocument();
  });

  test("disables save button when profile is unchanged", () => {
    renderWithProviders(<Account />);

    expect(
      screen.getByRole("button", {
        name: /save changes/i,
      }),
    ).toBeDisabled();
  });

  test("enables save button when display name changes", () => {
    renderWithProviders(<Account />);

    fireEvent.change(
      screen.getByLabelText(/display name/i),
      {
        target: {
          value: "Updated User",
        },
      },
    );

    expect(
      screen.getByRole("button", {
        name: /save changes/i,
      }),
    ).toBeEnabled();
  });

  test("requires age confirmation before enabling adult content", () => {
    renderWithProviders(<Account />);

    fireEvent.click(
      screen.getByRole("checkbox", {name: /show adult content/i}),
    );

    expect(
      screen.getByText(/age confirmation required/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", {
        name: /save changes/i,
      }),
    ).toBeDisabled();

    fireEvent.click(
      screen.getByLabelText(/i confirm that i am at least 18 years old/i),
    );

    expect(
      screen.getByRole("button", {
        name: /save changes/i,
      }),
    ).toBeEnabled();
  });

  test("submits the adult-content opt-in and age confirmation", async () => {
    renderWithProviders(<Account />);

    fireEvent.click(
      screen.getByRole("checkbox", {name: /show adult content/i}),
    );
    fireEvent.click(
      screen.getByLabelText(/i confirm that i am at least 18 years old/i),
    );
    fireEvent.click(
      screen.getByRole("button", {
        name: /save changes/i,
      }),
    );

    await waitFor(() => {
      expect(mocks.mutateAsync).toHaveBeenCalledWith({
        show_adult_content: true,
        confirm_adult_content_age: true,
      });
    });
  });

  test("allows an opted-in user to disable adult content immediately", async () => {
    mocks.useMe.mockReturnValue({
      data: {
        ...user,
        show_adult_content: true,
      },
      isLoading: false,
    });

    renderWithProviders(<Account />);

    const preference = screen.getByRole("checkbox", {
      name: /show adult content/i,
    });
    expect(preference).toBeChecked();

    fireEvent.click(preference);
    expect(
      screen.queryByText(/age confirmation required/i),
    ).not.toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", {
        name: /save changes/i,
      }),
    );

    await waitFor(() => {
      expect(mocks.mutateAsync).toHaveBeenCalledWith({
        show_adult_content: false,
      });
    });
  });

  test("submits updated display name", async () => {
    renderWithProviders(<Account />);

    fireEvent.change(
      screen.getByLabelText(/display name/i),
      {
        target: {
          value: "Updated User",
        },
      },
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: /save changes/i,
      }),
    );

    await waitFor(() => {
      expect(
        mocks.mutateAsync,
      ).toHaveBeenCalledWith({
        displayname: "Updated User",
      });
    });
  });

  test("trims display name before submitting", async () => {
    renderWithProviders(<Account />);

    fireEvent.change(
      screen.getByLabelText(/display name/i),
      {
        target: {
          value: "   Updated User   ",
        },
      },
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: /save changes/i,
      }),
    );

    await waitFor(() => {
      expect(
        mocks.mutateAsync,
      ).toHaveBeenCalledWith({
        displayname: "Updated User",
      });
    });
  });

  test("does not allow saving an empty display name", () => {
    renderWithProviders(<Account />);

    fireEvent.change(
      screen.getByLabelText(/display name/i),
      {
        target: {
          value: "   ",
        },
      },
    );

    expect(
      screen.getByRole("button", {
        name: /save changes/i,
      }),
    ).toBeDisabled();
  });

  test("does not allow saving a display name shorter than four characters", () => {
    renderWithProviders(<Account />);

    fireEvent.change(
      screen.getByLabelText(/display name/i),
      {
        target: {
          value: "abc",
        },
      },
    );

    expect(
      screen.getByText(
        /display name must be between 4 and 64 characters/i,
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("button", {
        name: /save changes/i,
      }),
    ).toBeDisabled();
  });

  test("opens the username editor", () => {
    renderWithProviders(<Account />);

    fireEvent.click(
      screen.getByRole("button", {
        name: /change username/i,
      }),
    );

    expect(
      screen.getByLabelText(/^username$/i),
    ).toHaveValue("testuser");

    expect(
      screen.getByRole("button", {
        name: /cancel username change/i,
      }),
    ).toBeInTheDocument();
  });

  test("requires confirmation before changing username", async () => {
    renderWithProviders(<Account />);

    fireEvent.click(
      screen.getByRole("button", {
        name: /change username/i,
      }),
    );

    fireEvent.change(
      screen.getByLabelText(/^username$/i),
      {
        target: {
          value: "updateduser",
        },
      },
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: /review changes/i,
      }),
    );

    expect(
      mocks.mutateAsync,
    ).not.toHaveBeenCalled();

    expect(
      screen.getByText(
        /confirm username change/i,
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        /will not be able to change your username again for 30 days/i,
      ),
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", {
        name: /confirm and save/i,
      }),
    );

    await waitFor(() => {
      expect(
        mocks.mutateAsync,
      ).toHaveBeenCalledWith({
        username: "updateduser",
      });
    });
  });

  test("trims username before submitting", async () => {
    renderWithProviders(<Account />);

    fireEvent.click(
      screen.getByRole("button", {
        name: /change username/i,
      }),
    );

    fireEvent.change(
      screen.getByLabelText(/^username$/i),
      {
        target: {
          value: "   updateduser   ",
        },
      },
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: /review changes/i,
      }),
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: /confirm and save/i,
      }),
    );

    await waitFor(() => {
      expect(
        mocks.mutateAsync,
      ).toHaveBeenCalledWith({
        username: "updateduser",
      });
    });
  });

  test("submits username and display name together", async () => {
    renderWithProviders(<Account />);

    fireEvent.change(
      screen.getByLabelText(/display name/i),
      {
        target: {
          value: "Updated Display",
        },
      },
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: /change username/i,
      }),
    );

    fireEvent.change(
      screen.getByLabelText(/^username$/i),
      {
        target: {
          value: "updateduser",
        },
      },
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: /review changes/i,
      }),
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: /confirm and save/i,
      }),
    );

    await waitFor(() => {
      expect(
        mocks.mutateAsync,
      ).toHaveBeenCalledWith({
        displayname: "Updated Display",
        username: "updateduser",
      });
    });
  });

  test("does not submit a username shorter than four characters", () => {
    renderWithProviders(<Account />);

    fireEvent.click(
      screen.getByRole("button", {
        name: /change username/i,
      }),
    );

    fireEvent.change(
      screen.getByLabelText(/^username$/i),
      {
        target: {
          value: "abc",
        },
      },
    );

    expect(
      screen.getByText(
        /username must be between 4 and 64 characters/i,
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("button", {
        name: /review changes/i,
      }),
    ).toBeDisabled();
  });

  test("cancels username editing", () => {
    renderWithProviders(<Account />);

    fireEvent.click(
      screen.getByRole("button", {
        name: /change username/i,
      }),
    );

    fireEvent.change(
      screen.getByLabelText(/^username$/i),
      {
        target: {
          value: "updateduser",
        },
      },
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: /cancel username change/i,
      }),
    );

    expect(
      screen.queryByLabelText(/^username$/i),
    ).not.toBeInTheDocument();

    expect(
      screen.getByText("testuser"),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("button", {
        name: /change username/i,
      }),
    ).toBeEnabled();
  });

  test("disables username changes during the cooldown", () => {
    mocks.useMe.mockReturnValue({
      data: {
        ...user,
        username_changed_at: new Date(
          Date.now() - 5 * DAY_MS,
        ).toISOString(),
      },
      isLoading: false,
    });

    renderWithProviders(<Account />);

    const changeButton =
      screen.getByRole("button", {
        name: /username change unavailable/i,
      });

    expect(changeButton).toBeDisabled();

    expect(
      screen.getByText(
        /you can change your username again on/i,
      ),
    ).toBeInTheDocument();

    expect(
      screen.queryByLabelText(/^username$/i),
    ).not.toBeInTheDocument();
  });

  test("allows username changes after the cooldown expires", () => {
    mocks.useMe.mockReturnValue({
      data: {
        ...user,
        username_changed_at: new Date(
          Date.now() - 31 * DAY_MS,
        ).toISOString(),
      },
      isLoading: false,
    });

    renderWithProviders(<Account />);

    expect(
      screen.getByRole("button", {
        name: /change username/i,
      }),
    ).toBeEnabled();

    expect(
      screen.queryByText(
        /you can change your username again on/i,
      ),
    ).not.toBeInTheDocument();
  });

  test("allows display name changes during username cooldown", async () => {
    mocks.useMe.mockReturnValue({
      data: {
        ...user,
        username_changed_at: new Date(
          Date.now() - 5 * DAY_MS,
        ).toISOString(),
      },
      isLoading: false,
    });

    renderWithProviders(<Account />);

    fireEvent.change(
      screen.getByLabelText(/display name/i),
      {
        target: {
          value: "Updated Display",
        },
      },
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: /save changes/i,
      }),
    );

    await waitFor(() => {
      expect(
        mocks.mutateAsync,
      ).toHaveBeenCalledWith({
        displayname: "Updated Display",
      });
    });
  });

  test("shows saving state", () => {
    mocks.useUpdateProfile.mockReturnValue({
      mutateAsync: mocks.mutateAsync,
      reset: mocks.reset,
      isPending: true,
      isSuccess: false,
      error: null,
    });

    renderWithProviders(<Account />);

    expect(
      screen.getByRole("button", {
        name: /saving/i,
      }),
    ).toBeDisabled();
  });

  test("shows success message after profile update", () => {
    mocks.useUpdateProfile.mockReturnValue({
      mutateAsync: mocks.mutateAsync,
      reset: mocks.reset,
      isPending: false,
      isSuccess: true,
      error: null,
    });

    renderWithProviders(<Account />);

    expect(
      screen.getByText(/profile updated/i),
    ).toBeInTheDocument();
  });

  test("shows generic error message when update fails", () => {
    mocks.useUpdateProfile.mockReturnValue({
      mutateAsync: mocks.mutateAsync,
      reset: mocks.reset,
      isPending: false,
      isSuccess: false,
      error: new Error("Something failed"),
    });

    renderWithProviders(<Account />);

    expect(
      screen.getByText(
        /failed to update profile/i,
      ),
    ).toBeInTheDocument();
  });
});
