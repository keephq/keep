// The error.js file convention allows you to gracefully handle unexpected runtime errors.
// The way it does this is by automatically wrap a route segment and its nested children in a React Error Boundary.
// https://nextjs.org/docs/app/api-reference/file-conventions/error
// https://nextjs.org/docs/app/building-your-application/routing/error-handling#how-errorjs-works

"use client";
import { useEffect } from "react";
import { Title, Subtitle } from "@tremor/react";
import { Button, Text } from "@tremor/react";
import { KeepApiError } from "@/shared/api";
import * as Sentry from "@sentry/nextjs";
import { useSignOut } from "@/shared/lib/hooks/useSignOut";
import { KeepApiHealthError } from "@/shared/api/KeepApiError";
import { useHealth } from "@/shared/lib/hooks/useHealth";
import { KeepLogoError } from "@/shared/ui/KeepLogoError";

export function ErrorComponent({
  error: originalError,
  reset,
}: {
  error: Error | KeepApiError;
  reset?: () => void;
}) {
  const signOut = useSignOut();
  const { isHealthy } = useHealth();

  useEffect(() => {
    Sentry.captureException(originalError);
  }, [originalError]);

  const error = isHealthy ? originalError : new KeepApiHealthError();

  return (
    <div className="flex min-w-0 w-auto mx-auto shrink flex-col items-center justify-center h-full text-center gap-4">
      <KeepLogoError />
      <div>
        <Title>{error.message || "An error occurred"}</Title>
        {error instanceof KeepApiError && error.proposedResolution && (
          <Subtitle>{error.proposedResolution}</Subtitle>
        )}
      </div>
      <code className="text-gray-600 text-left bg-gray-100 p-2 rounded-md">
        {error instanceof KeepApiError && (
          <>
            {error.statusCode && <p>Status Code: {error.statusCode}</p>}
            {error.message && <p>Message: {error.message}</p>}
            {error.url && <p>URL: {error.url}</p>}
          </>
        )}
      </code>
      <div className="flex gap-2">
        {error instanceof KeepApiError && error.statusCode === 401 ? (
          <Button onClick={signOut} color="orange" variant="secondary">
            <Text>Sign Out</Text>
          </Button>
        ) : (
          <Button
            onClick={() => {
              if (reset) {
                reset();
              } else {
                window.location.reload();
              }
            }}
            color="orange"
            variant="primary"
          >
            Try again
          </Button>
        )}{" "}
        <Button
          color="orange"
          variant="secondary"
          onClick={() => window.open("https://slack.keephq.dev/", "_blank")}
        >
          Slack Us
        </Button>
      </div>
    </div>
  );
}
