"use client";

import { SWRConfig } from "swr";

export function ConfigProvider({
  children,
  config,
}: {
  children: React.ReactNode;
  config: any;
}) {
  return (
    <SWRConfig
      value={{
        fallback: {
          "/api/config": config,
        },
      }}
    >
      {children}
    </SWRConfig>
  );
}
