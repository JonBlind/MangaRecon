import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  removeQueries: vi.fn(),
}));

vi.mock("../../src/app/queryClient", () => ({
  queryClient: {
    removeQueries: mocks.removeQueries,
  },
}));

const originalLocation = window.location;

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
    },
  });
}

function textResponse(body: string, status = 200) {
  return new Response(body, {
    status,
    headers: {
      "Content-Type": "text/plain",
    },
  });
}

function mockLocation(pathname: string, search = "", hash = "") {
  const assign = vi.fn();

  Object.defineProperty(window, "location", {
    configurable: true,
    value: {
      pathname,
      search,
      hash,
      assign,
    },
  });

  return assign;
}

async function loadHttpModule() {
  vi.resetModules();
  vi.stubEnv("VITE_API_BASE_URL", "http://localhost:8000");
  return import("../../src/api/http");
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubGlobal("fetch", vi.fn());

  Object.defineProperty(window, "location", {
    configurable: true,
    value: originalLocation,
  });

  sessionStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();

  Object.defineProperty(window, "location", {
    configurable: true,
    value: originalLocation,
  });
});

describe("apiFetch", () => {
  test("throws during module load when VITE_API_BASE_URL is missing", async () => {
    vi.resetModules();
    vi.stubEnv("VITE_API_BASE_URL", "");

    await expect(import("../../src/api/http")).rejects.toThrow(
      /vite_api_base_url is not set/i
    );
  });

  test("sends request with base url, credentials, and default json content type", async () => {
    const { apiFetch } = await loadHttpModule();

    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({
        status: "success",
        data: {
          ok: true,
        },
      })
    );

    await expect(apiFetch("/healthz")).resolves.toEqual({
      status: "success",
      data: {
        ok: true,
      },
    });

    expect(fetch).toHaveBeenCalledWith("http://localhost:8000/healthz", {
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
      },
    });
  });

  test("preserves provided request options and merges headers", async () => {
    const { apiFetch } = await loadHttpModule();

    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({
        status: "success",
        data: {
          created: true,
        },
      })
    );

    await apiFetch("/collections", {
      method: "POST",
      headers: {
        "X-Test": "yes",
      },
      body: JSON.stringify({
        collection_name: "Favorites",
      }),
    });

    expect(fetch).toHaveBeenCalledWith("http://localhost:8000/collections", {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "X-Test": "yes",
      },
      body: JSON.stringify({
        collection_name: "Favorites",
      }),
    });
  });

  test("allows caller content type header to override default json header", async () => {
    const { apiFetch } = await loadHttpModule();

    const body = new URLSearchParams();
    body.set("username", "test@example.com");
    body.set("password", "password123");

    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({
        status: "success",
        data: null,
      })
    );

    await apiFetch("/auth/jwt/login", {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body,
    });

    expect(fetch).toHaveBeenCalledWith("http://localhost:8000/auth/jwt/login", {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body,
    });
  });

  test("handles empty successful response body", async () => {
    const { apiFetch } = await loadHttpModule();

    vi.mocked(fetch).mockResolvedValueOnce(textResponse("", 200));

    await expect(apiFetch("/empty")).resolves.toBeNull();
  });

  test("throws ApiRequestError with message from non-generic error response", async () => {
    const { apiFetch } = await loadHttpModule();

    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse(
        {
          status: "error",
          message: "Collection already exists.",
          data: {
            detail: "DUPLICATE_COLLECTION",
          },
        },
        409
      )
    );

    await expect(apiFetch("/collections")).rejects.toMatchObject({
      name: "ApiRequestError",
      message: "Collection already exists.",
      statusCode: 409,
      errorCode: "DUPLICATE_COLLECTION",
      errorData: {
        detail: "DUPLICATE_COLLECTION",
      },
    });
  });

  test("extracts generic string detail as error message", async () => {
    const { apiFetch } = await loadHttpModule();

    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse(
        {
          status: "error",
          message: "Error",
          detail: "Invalid collection id.",
        },
        400
      )
    );

    await expect(apiFetch("/collections/bad")).rejects.toMatchObject({
      message: "Invalid collection id.",
      statusCode: 400,
      errorCode: "Invalid collection id.",
    });
  });

  test("extracts validation detail array with location", async () => {
    const { apiFetch } = await loadHttpModule();

    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse(
        {
          status: "error",
          message: "Validation error",
          detail: [
            {
              loc: ["body", "collection_name"],
              msg: "Field required",
            },
          ],
        },
        422
      )
    );

    await expect(apiFetch("/collections")).rejects.toMatchObject({
      message: "collection_name: Field required",
      statusCode: 422,
    });
  });

  test("extracts validation detail array without location", async () => {
    const { apiFetch } = await loadHttpModule();

    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse(
        {
          status: "error",
          message: "Validation error",
          detail: [
            {
              msg: "Invalid value",
            },
          ],
        },
        422
      )
    );

    await expect(apiFetch("/collections")).rejects.toMatchObject({
      message: "Invalid value",
      statusCode: 422,
    });
  });

  test("extracts generic detail object reason", async () => {
    const { apiFetch } = await loadHttpModule();

    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse(
        {
          status: "error",
          message: "Error",
          detail: {
            reason: "Rate limited.",
          },
        },
        429
      )
    );

    await expect(apiFetch("/limited")).rejects.toMatchObject({
      message: "Rate limited.",
      statusCode: 429,
    });
  });

  test("extracts generic detail object message", async () => {
    const { apiFetch } = await loadHttpModule();

    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse(
        {
          status: "error",
          message: "Error",
          detail: {
            message: "Object message.",
          },
        },
        400
      )
    );

    await expect(apiFetch("/bad")).rejects.toMatchObject({
      message: "Object message.",
    });
  });

  test("extracts generic detail object code", async () => {
    const { apiFetch } = await loadHttpModule();

    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse(
        {
          status: "error",
          message: "Error",
          detail: {
            code: "SOME_ERROR_CODE",
          },
        },
        400
      )
    );

    await expect(apiFetch("/bad")).rejects.toMatchObject({
      message: "SOME_ERROR_CODE",
    });
  });

  test("falls back when error response has invalid json", async () => {
    const { apiFetch } = await loadHttpModule();

    vi.mocked(fetch).mockResolvedValueOnce(textResponse("not json", 500));

    await expect(apiFetch("/broken")).rejects.toMatchObject({
      message: "Request failed (500)",
      statusCode: 500,
    });
  });

  test("throws maintenance error and redirects to maintenance page on 503", async () => {
    const { apiFetch } = await loadHttpModule();
    const assign = mockLocation("/collections", "?page=1", "#top");

    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse(
        {
          status: "error",
          message: "Service unavailable",
        },
        503
      )
    );

    await expect(apiFetch("/collections")).rejects.toMatchObject({
      message: "Service temporarily unavailable",
      statusCode: 503,
      errorCode: "TEMPORARILY_UNAVAILABLE",
    });

    expect(sessionStorage.getItem("preMaintenancePath")).toBe(
      "/collections?page=1#top"
    );
    expect(assign).toHaveBeenCalledWith("/maintenance");
  });

  test("does not redirect again when already on maintenance page", async () => {
    const { apiFetch } = await loadHttpModule();
    const assign = mockLocation("/maintenance");

    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse(
        {
          status: "error",
          message: "Service unavailable",
        },
        503
      )
    );

    await expect(apiFetch("/readyz")).rejects.toMatchObject({
      statusCode: 503,
    });

    expect(assign).not.toHaveBeenCalled();
  });

  test("throws 401 without redirect on unprotected path", async () => {
    const { apiFetch } = await loadHttpModule();
    const assign = mockLocation("/search");

    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse(
        {
          status: "error",
          message: "Unauthorized",
        },
        401
      )
    );

    await expect(apiFetch("/profiles/me")).rejects.toMatchObject({
      message: "Unauthorized",
      statusCode: 401,
      errorCode: "UNAUTHORIZED",
    });

    expect(mocks.removeQueries).not.toHaveBeenCalled();
    expect(assign).not.toHaveBeenCalled();
  });

  test("redirects to login on 401 from protected collections path", async () => {
    const { apiFetch } = await loadHttpModule();
    const assign = mockLocation("/collections", "?page=2");

    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse(
        {
          status: "error",
          message: "Unauthorized",
        },
        401
      )
    );

    await expect(apiFetch("/collections")).rejects.toMatchObject({
      statusCode: 401,
    });

    expect(mocks.removeQueries).toHaveBeenCalledWith({
      queryKey: ["me"],
    });

    expect(sessionStorage.getItem("postLoginRedirect")).toBe(
      "/collections?page=2"
    );
    expect(assign).toHaveBeenCalledWith("/login");
  });

  test("redirects to login on 401 from protected recommendations path", async () => {
    const { apiFetch } = await loadHttpModule();
    const assign = mockLocation("/recommendations", "?collectionId=1");

    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse(
        {
          status: "error",
          message: "Unauthorized",
        },
        401
      )
    );

    await expect(apiFetch("/recommendations/1")).rejects.toMatchObject({
      statusCode: 401,
    });

    expect(mocks.removeQueries).toHaveBeenCalledWith({
      queryKey: ["me"],
    });

    expect(sessionStorage.getItem("postLoginRedirect")).toBe(
      "/recommendations?collectionId=1"
    );
    expect(assign).toHaveBeenCalledWith("/login");
  });

  test("does not redirect again when already on login page", async () => {
    const { apiFetch } = await loadHttpModule();
    const assign = mockLocation("/login");

    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse(
        {
          status: "error",
          message: "Unauthorized",
        },
        401
      )
    );

    await expect(apiFetch("/collections")).rejects.toMatchObject({
      statusCode: 401,
    });

    expect(assign).not.toHaveBeenCalled();
  });
});

describe("ApiRequestError", () => {
  test("stores status code, error code, and error data", async () => {
    const { ApiRequestError } = await loadHttpModule();

    const errorData = {
      detail: "Extra info",
    };

    const error = new ApiRequestError(
      "Failed",
      400,
      "BAD_REQUEST",
      errorData
    );

    expect(error).toBeInstanceOf(Error);
    expect(error.name).toBe("ApiRequestError");
    expect(error.message).toBe("Failed");
    expect(error.statusCode).toBe(400);
    expect(error.errorCode).toBe("BAD_REQUEST");
    expect(error.errorData).toBe(errorData);
  });
});