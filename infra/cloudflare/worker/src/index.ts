const PUBLIC_HOSTNAME = "api.mangarecon.com";
const LAMBDA_HOSTNAME_SUFFIX = ".lambda-url.us-east-1.on.aws";
const ORIGIN_VERIFY_HEADER = "X-MangaRecon-Origin-Verify";
const CLIENT_ADDRESS_HEADER = "CF-Connecting-IP";

type Bindings = {
  BACKEND_ORIGIN_URL: string;
  ORIGIN_VERIFY_SECRET: string;
};

function errorResponse(
  status: number,
  message: string,
  detail: string,
): Response {
  return Response.json(
    {
      status: "error",
      data: {},
      message,
      detail,
    },
    {
      status,
      headers: {
        "Cache-Control": "no-store",
      },
    },
  );
}

function resolveBackendOrigin(value: string): URL | null {
  let origin: URL;

  try {
    origin = new URL(value);
  } catch {
    return null;
  }

  if (
    origin.protocol !== "https:" ||
    !origin.hostname.endsWith(LAMBDA_HOSTNAME_SUFFIX) ||
    origin.username ||
    origin.password ||
    origin.search ||
    origin.hash
  ) {
    return null;
  }

  return origin;
}

export default {
  async fetch(request, env): Promise<Response> {
    const incomingUrl = new URL(request.url);

    if (incomingUrl.hostname !== PUBLIC_HOSTNAME) {
      return errorResponse(404, "Not found", "NOT_FOUND");
    }

    const backendOrigin = resolveBackendOrigin(env.BACKEND_ORIGIN_URL);
    const clientAddress = request.headers.get(CLIENT_ADDRESS_HEADER);

    if (
      backendOrigin === null ||
      !env.ORIGIN_VERIFY_SECRET ||
      !clientAddress
    ) {
      return errorResponse(
        503,
        "Service unavailable",
        "TEMPORARILY_UNAVAILABLE",
      );
    }

    const upstreamUrl = new URL(
      `${incomingUrl.pathname}${incomingUrl.search}`,
      backendOrigin,
    );

    const upstreamHeaders = new Headers(request.headers);
    upstreamHeaders.delete("host");
    upstreamHeaders.delete("content-length");
    upstreamHeaders.set(ORIGIN_VERIFY_HEADER, env.ORIGIN_VERIFY_SECRET);
    upstreamHeaders.set(CLIENT_ADDRESS_HEADER, clientAddress);

    const upstreamRequest: RequestInit = {
      method: request.method,
      headers: upstreamHeaders,
      redirect: "manual",
    };

    if (request.method !== "GET" && request.method !== "HEAD") {
      upstreamRequest.body = request.body;
    }

    try {
      return await fetch(upstreamUrl, upstreamRequest);
    } catch {
      return errorResponse(
        502,
        "Upstream service unavailable",
        "UPSTREAM_UNAVAILABLE",
      );
    }
  },
} satisfies ExportedHandler<Bindings>;