import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import { useMe } from "../../src/hooks/useMe";

const mocks = vi.hoisted(() => ({
  me: vi.fn(),
}));

vi.mock("../../src/api/auth", () => ({
  me: mocks.me,
}));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.me.mockResolvedValue(null);
});

describe("useMe", () => {
  test("does not request the current user until enabled", async () => {
    const { rerender } = renderHook(({ enabled }) => useMe(enabled), {
      initialProps: { enabled: false },
      wrapper: createWrapper(),
    });

    expect(mocks.me).not.toHaveBeenCalled();

    rerender({ enabled: true });

    await waitFor(() => {
      expect(mocks.me).toHaveBeenCalledTimes(1);
    });
  });
});
