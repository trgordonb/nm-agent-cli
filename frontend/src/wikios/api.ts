// Ported from wiki-os src/client/api.ts (MIT), with the /wapi adapter:
// every upstream path the client knows as /api/... is issued against the
// FastAPI proxy at /wapi/api/... (server.py forwards /wapi/* to the engine).
// fetchJson still throws `Response` objects (not Errors) on !ok — the wiki
// views key on `error instanceof Response && status === 409` for setup state.

const WAPI_PREFIX = "/wapi";

function toWapi(path: string): string {
  return path.startsWith("/api/") ? `${WAPI_PREFIX}${path}` : path;
}

export async function fetchJson<T>(input: string, init?: RequestInit): Promise<T> {
  const response = await fetch(toWapi(input), {
    ...init,
    headers: {
      accept: "application/json",
      ...init?.headers,
    },
  });

  const contentType = response.headers.get("content-type") ?? "";
  const payload = contentType.includes("application/json")
    ? (await response.json()) as unknown
    : await response.text();

  if (!response.ok) {
    const message =
      typeof payload === "string"
        ? payload
        : payload &&
            typeof payload === "object" &&
            "error" in payload &&
            typeof payload.error === "string"
          ? payload.error
          : response.statusText;

    throw new Response(message, {
      status: response.status,
      statusText: response.statusText,
    });
  }

  return payload as T;
}

export function isSetupRequiredResponse(error: unknown) {
  return error instanceof Response && error.status === 409;
}

export function isNotFoundResponse(error: unknown) {
  return error instanceof Response && error.status === 404;
}
