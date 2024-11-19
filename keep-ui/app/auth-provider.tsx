"use client";

import { Session } from "next-auth";
import { SessionProvider } from "next-auth/react";

declare global {
  interface Window {
    __NEXT_AUTH_SESSION__?: Session | null;
  }
}

type Props = {
  children?: React.ReactNode;
  session?: Session | null;
};

export const NextAuthProvider = ({ children, session }: Props) => {
  // Hydrate session on mount
  if (typeof window !== "undefined" && !!session) {
    window.__NEXT_AUTH_SESSION__ = session;
  }

  return <SessionProvider>{children}</SessionProvider>;
};
