"use client";
import { useState, useEffect } from "react";
import { useSession as useNextAuthSession } from "next-auth/react";
import type { Session } from "next-auth";
import type { UseSessionOptions, SessionContextValue } from "next-auth/react";

export function useHydratedSession(
  options?: UseSessionOptions<boolean>
): SessionContextValue {
  const [isHydrated, setIsHydrated] = useState(false);
  const session = useNextAuthSession(options);
  useEffect(() => {
    setIsHydrated(true);
  }, []);
  // Ensure we're in browser environment
  const isBrowser = typeof window !== "undefined";
  // On first render, return hydrated session if available
  if (
    (!isHydrated || session.status === "loading") &&
    isBrowser &&
    window.__NEXT_AUTH_SESSION__ !== null &&
    window.__NEXT_AUTH_SESSION__ !== undefined
  ) {
    return {
      data: window.__NEXT_AUTH_SESSION__,
      status: "authenticated" as const,
      update: session.update,
    } satisfies SessionContextValue;
  }
  return session;
}
