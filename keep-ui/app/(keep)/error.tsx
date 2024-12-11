// The error.js file convention allows you to gracefully handle unexpected runtime errors.
// The way it does this is by automatically wrap a route segment and its nested children in a React Error Boundary.
// https://nextjs.org/docs/app/api-reference/file-conventions/error
// https://nextjs.org/docs/app/building-your-application/routing/error-handling#how-errorjs-works

"use client";
import Image from "next/image";
import "./error.css";
import { useEffect } from "react";
import { Title, Subtitle } from "@tremor/react";
import { Button, Text } from "@tremor/react";
import { KeepApiError } from "@/shared/api";
import * as Sentry from "@sentry/nextjs";
import { useSignOut } from "@/shared/lib/hooks/useSignOut";

export default function ErrorComponent({
  error,
  reset,
}: {
  error: Error | KeepApiError;
  reset: () => void;
}) {
  const signOut = useSignOut();

  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <div className="error-container">
      <Title>
        {error instanceof KeepApiError
          ? "An error occurred while fetching data from the backend"
          : error.message || "An error occurred"}
      </Title>
      <div className="code-container">
        <code>
          {error instanceof KeepApiError && (
            <div className="mt-4">
              Status Code: {error.statusCode}
              <br />
              Message: {error.message}
              <br />
              URL: {error.url}
            </div>
          )}
        </code>
      </div>
      {error instanceof KeepApiError && error.proposedResolution && (
        <Subtitle className="mt-4">{error.proposedResolution}</Subtitle>
      )}

      <div className="error-image">
        <Image src="/keep.svg" alt="Keep" width={150} height={150} />
      </div>
      {error instanceof KeepApiError && error.statusCode === 401 ? (
        <Button
          onClick={signOut}
          color="orange"
          variant="secondary"
          className="mt-4 border border-orange-500 text-orange-500"
        >
          <Text>Sign Out</Text>
        </Button>
      ) : (
        <Button
          onClick={() => {
            console.log("Refreshing...");
            window.location.reload();
          }}
          color="orange"
          variant="secondary"
        >
          Try again
        </Button>
      )}
    </div>
  );
}
