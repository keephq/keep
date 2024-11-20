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

export function useHydratedSession() {
  const [isHydrated, setIsHydrated] = useState(false);
  const session = useSession();

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
