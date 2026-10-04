// Adapted from wiki-os route-error-boundary.tsx + error-state-view/not-found
// (MIT). Upstream used react-router's error boundary + loader redirects; here
// fetch failures surface as component state, so this is a plain view driven by
// props.

export function WikiErrorView({
  status,
  message,
  onHome,
}: {
  status?: number;
  message: string;
  onHome: () => void;
}) {
  const headline = status === 404 ? "Page not found" : "Local wiki unavailable";
  const detail =
    status === 409
      ? "The wiki engine needs a little setup before this page is ready."
      : status === 503
        ? "The wiki engine is getting things ready. Please try again in a moment."
        : status !== undefined && status >= 500
          ? "This page could not be loaded right now. Please try again in a moment."
          : message;

  return (
    <main className="flex h-full flex-col items-center justify-center gap-6 px-4 text-center">
      <div className="space-y-2">
        <p className="text-sm uppercase tracking-[0.2em] text-[var(--muted-foreground)]">
          {status ?? "error"}
        </p>
        <h1 className="text-3xl font-semibold">{headline}</h1>
        <p className="max-w-md text-[var(--muted-foreground)]">{detail}</p>
      </div>
      <button
        type="button"
        onClick={onHome}
        className="inline-flex h-10 items-center justify-center rounded-md bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] transition-opacity hover:opacity-90"
      >
        Back to the wiki
      </button>
    </main>
  );
}

export function statusOf(error: unknown): number | undefined {
  return error instanceof Response ? error.status : undefined;
}

export function messageOf(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  if (error instanceof Response) {
    return error.statusText || "Something went wrong while opening this page.";
  }
  return "Something went wrong while opening this page.";
}
