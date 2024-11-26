"use client";

import { useCallback } from "react";
import { signOut } from "next-auth/react";
import * as Sentry from "@sentry/nextjs";
import posthog from "posthog-js";
import { useConfig } from "@/utils/hooks/useConfig";

export function useSignOut() {
  const { data: configData } = useConfig();

  return useCallback(() => {
    if (!configData) {
      return;
    }

    if (configData?.SENTRY_DISABLED !== "true") {
      Sentry.setUser(null);
    }

    if (configData?.POSTHOG_DISABLED !== "true") {
      posthog.reset();
    }

    signOut();
  }, [configData]);
}
