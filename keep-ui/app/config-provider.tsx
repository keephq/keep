"use client";

import { createContext } from "react";

// Create the context with undefined as initial value
export const ConfigContext = createContext<any | undefined>(undefined);

// Create a provider component
export function ConfigProvider({
  children,
  config,
}: {
  children: React.ReactNode;
  config: any;
}) {
  return (
    <ConfigContext.Provider value={config}>{children}</ConfigContext.Provider>
  );
}
