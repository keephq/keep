"use client";

import { useSession as useNextAuthSession } from "next-auth/react";
import { useState, useEffect } from "react";

declare global {
  interface Window {
    __NEXT_AUTH_SESSION__?: any;
  }
}

export function useHydratedSession() {
  const [isHydrated, setIsHydrated] = useState(false);
  const session = useNextAuthSession();

  useEffect(() => {
    setIsHydrated(true);
  }, []);

  // On first render, return hydrated session if available
  if (
    !isHydrated &&
    typeof window !== "undefined" &&
    window.__NEXT_AUTH_SESSION__
  ) {
    return {
      data: window.__NEXT_AUTH_SESSION__,
      status: "authenticated",
      update: session.update,
    };
  }

  return session;
}
