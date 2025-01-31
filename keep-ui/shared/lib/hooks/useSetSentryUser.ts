"use client";

import { useConfig } from "utils/hooks/useConfig";
import * as Sentry from "@sentry/nextjs";
import { useEffect } from "react";
import { Session } from "next-auth";

type SentryUser = {
  id?: string;
  email?: string;
  username?: string;
  name?: string;  // Removed undefined since it's already optional
  tenant_id?: string;
}

export function useSetSentryUser({ session }: { session: Session | null }) {
  const { data: configData } = useConfig();

  useEffect(() => {
    if (configData?.SENTRY_DISABLED === "true") {
      return;
    }

    if (!session?.user) {
      return;
    }

    const sentryUser: SentryUser = {
      id: session.user.id,
      email: session.user.email ?? undefined,
      name: session.user.name ?? undefined,
      tenant_id: session.tenantId
    };

    Sentry.setUser(sentryUser);
  }, [session, configData]);
}
