"use client";

import { CopilotKit } from "@copilotkit/react-core";
import { ReactNode } from "react";

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <CopilotKit runtimeUrl="/api/copilotkit">
      <main>{children}</main>
    </CopilotKit>
  );
}
