"use client";

import { createContext } from "react";
import { InternalConfig } from "types/internal-config";

// Create the context with undefined as initial value
export const ConfigContext = createContext<InternalConfig | null>(null);

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
