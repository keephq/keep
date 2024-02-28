"use client";

import { ReactNode } from "react";
import { ThemeProvider } from "next-themes";
import { SessionProvider } from "next-auth/react";

type ProviderProps = {
  children: ReactNode;
};

export const Providers = ({ children }: ProviderProps) => {
  return (
    <ThemeProvider attribute="class">
      <SessionProvider>{children}</SessionProvider>
    </ThemeProvider>
  );
};
