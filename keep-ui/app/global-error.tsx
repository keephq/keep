"use client";

import { useEffect } from "react";
import * as Sentry from "@sentry/nextjs";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  // This boundary replaces the root layout, including all of its providers.
  // Keep it independent of session, configuration, and API hooks.
  return (
    <html lang="en">
      <body>
        <main>
          <h1>Something went wrong</h1>
          <p>{error.message || "An unexpected error occurred."}</p>
          {error.digest && <p>Error reference: {error.digest}</p>}
          <button onClick={reset}>Try again</button>
        </main>
      </body>
    </html>
  );
}
