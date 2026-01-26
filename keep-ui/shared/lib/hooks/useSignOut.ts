"use client";

import { useCallback } from "react";
import { signOut } from "next-auth/react";
import * as Sentry from "@sentry/nextjs";
import posthog from "posthog-js";
import { useConfig } from "@/utils/hooks/useConfig";
import { AuthType } from "@/utils/authenticationType";

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

    // For OAUTH2PROXY auth, redirect to oauth2-proxy's sign_out endpoint
    // This properly clears the oauth2-proxy session and redirects to the IdP logout
    if (configData?.AUTH_TYPE === AuthType.OAUTH2PROXY) {
      window.location.href = "/oauth2/sign_out";
      return;
    }

    signOut();
  }, [configData]);
}
