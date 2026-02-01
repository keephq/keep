"use client";

import { useConfig } from "@/utils/hooks/useConfig";
import posthog from "posthog-js";
import { PostHogProvider } from "posthog-js/react";
import { useEffect } from "react";

export function PHProvider({ children }: { children: React.ReactNode }) {
  const { data: config } = useConfig();

  useEffect(() => {
    if (!config || config.POSTHOG_DISABLED === "true" || !config.POSTHOG_KEY) {
      return;
    }
    posthog.init(config.POSTHOG_KEY!, {
      api_host: config.POSTHOG_HOST,
      ui_host: config.POSTHOG_HOST,
    });
  }, [config]);

  return <PostHogProvider client={posthog}>{children}</PostHogProvider>;
}
