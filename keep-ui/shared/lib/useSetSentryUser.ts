"use client";

import { useConfig } from "utils/hooks/useConfig";
import * as Sentry from "@sentry/nextjs";
import { useEffect } from "react";
import { Session } from "next-auth";

export function useSetSentryUser({ session }: { session: Session | null }) {
  const { data: configData } = useConfig();

  useEffect(() => {
    if (configData?.SENTRY_DISABLED === "true") {
      return;
    }

    if (!session || !session.user) {
      return;
    }

    Sentry.setUser({ ...session.user, tenant_id: session.tenantId });
  }, [session, configData]);
}
