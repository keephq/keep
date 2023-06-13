"use client";

import { SessionProvider } from "next-auth/react";

type Props = {
  children?: React.ReactNode;
};

const isSingleTenant = process.env.NEXT_PUBLIC_AUTH_ENABLED == "false";

export const NextAuthProvider = ({ children }: Props) => {
  console.log("Initializing NextAuthProvider")
  return isSingleTenant ? (
    <>{children}</>
  ) : (
    <SessionProvider>{children}</SessionProvider>
  );
};
