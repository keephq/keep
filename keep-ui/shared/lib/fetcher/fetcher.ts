import { KeepApiError } from "@/shared/lib/api/KeepApiError";
import { InternalConfig } from "@/types/internal-config";
import { Session } from "next-auth";
import { getApiUrlFromConfig } from "../api/getApiUrlFromConfig";

// TODO: use axios, add retry logic
// TODO: create a custom hook for authenticated fetcher
export const fetcher = async (
  url: string,
  accessToken: string | undefined,
  requestInit: RequestInit = {}
) => {
  const response = await fetch(url, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
    ...requestInit,
  });

  // Ensure that the fetch was successful
  if (!response.ok) {
    // if the response has detail field, throw the detail field
    if (response.headers.get("content-type")?.includes("application/json")) {
      const data = await response.json();
      if (response.status === 401) {
        throw new KeepApiError(
          `${data.message || data.detail}`,
          url,
          `You probably just need to sign in again.`,
          response.status
        );
      }
      throw new KeepApiError(
        `${data.message || data.detail}`,
        url,
        `Please try again. If the problem persists, please contact support.`,
        response.status
      );
    }
    throw new Error("An error occurred while fetching the data.");
  }

  // Parse and return the JSON data
  return response.json();
};
