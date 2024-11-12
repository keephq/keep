// @ts-nocheck
import * as Sentry from "@sentry/nextjs";

export async function register() {
  if (
    process.env.SENTRY_DISABLED === "true" ||
    process.env.NODE_ENV === "development"
  ) {
    return;
  }

  if (process.env.NEXT_RUNTIME === "nodejs") {
    await import("./sentry.server.config");
  }

  if (process.env.NEXT_RUNTIME === "edge") {
    await import("./sentry.edge.config");
  }
}

// We need NextJS 15 to use this
export const onRequestError = Sentry.captureRequestError;
