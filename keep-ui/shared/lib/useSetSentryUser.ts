"use client";

import { useSession } from "next-auth/react";
import { useConfig } from "utils/hooks/useConfig";
import * as Sentry from "@sentry/nextjs";
import { useEffect } from "react";

export const useSetSentryUser = () => {
  const { data: session } = useSession();
  const { data: configData } = useConfig();

  useEffect(() => {
    if (configData?.SENTRY_DISABLED === "true") {
      return;
    }

    if (!session || !session.user) {
      return;
    }

    Sentry.setUser(session.user);
  }, [session, configData]);
};
