"use client";
import { useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import type { Session } from "next-auth";

// Define window augmentation for Next Auth session
declare global {
  interface Window {
    __NEXT_AUTH?: {
      session?: Session;
    };
  }
}

// useSession() returns undefined when rendered outside <SessionProvider>, e.g.
// in app/global-error.tsx, which replaces the root layout. Treat that as
// "loading" so callers such as useApi() never destructure undefined.
const NO_SESSION_PROVIDER: ReturnType<typeof useSession> = {
  data: null,
  status: "loading",
  update: async () => null,
};

export function useHydratedSession() {
  const [isHydrated, setIsHydrated] = useState(false);
  const session = useSession() ?? NO_SESSION_PROVIDER;

  useEffect(() => {
    setIsHydrated(true);
  }, []);

  // If we're in the browser and have a preloaded session
  if (
    !isHydrated &&
    typeof window !== "undefined" &&
    window.__NEXT_AUTH?.session
  ) {
    return {
      data: window.__NEXT_AUTH.session,
      status: "authenticated" as const,
      update: session.update,
    };
  }

  return session;
}
