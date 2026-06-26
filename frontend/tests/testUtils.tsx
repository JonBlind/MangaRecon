import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";

export function renderWithProviders(
  ui: ReactElement,
  options?: { withRouter?: boolean }
) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  const content = (
    <QueryClientProvider client={queryClient}>
      {options?.withRouter === false ? ui : <MemoryRouter>{ui}</MemoryRouter>}
    </QueryClientProvider>
  );

  return render(content);
}