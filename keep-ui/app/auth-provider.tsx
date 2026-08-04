"use client";

import { Session } from "next-auth";
import { SessionProvider } from "next-auth/react";

declare global {
  interface Window {
    __NEXT_AUTH?: {
      session?: Session;
    };
  }
}

type Props = {
  children?: React.ReactNode;
  session?: Session | null;
};

export const NextAuthProvider = ({ children, session }: Props) => {
  // Hydrate session on mount so useHydratedSession can read it synchronously
  if (typeof window !== "undefined" && !!session) {
    window.__NEXT_AUTH = { session };
  }

  // Pass the server-resolved session as the initial data so SessionProvider
  // does not need to fetch it again, preventing a flash of loading/undefined
  // state that crashes consumers that destructure `session.data`.
  return <SessionProvider session={session}>{children}</SessionProvider>;
};
