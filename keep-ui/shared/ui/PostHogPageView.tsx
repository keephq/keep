// app/PostHogPageView.tsx
"use client";

import { usePathname, useSearchParams } from "next/navigation";
import { useEffect } from "react";
import { usePostHog } from "posthog-js/react";
import { useConfig } from "@/utils/hooks/useConfig";
import { useHydratedSession as useSession } from "../lib/hooks/useHydratedSession";
import { NoAuthUserEmail } from "@/utils/authenticationType";

export default function PostHogPageView(): null {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const posthog = usePostHog();
  const { data: config } = useConfig();
  const { data: session } = useSession();

  const isPosthogDisabled =
    config?.POSTHOG_DISABLED === "true" || !config?.POSTHOG_KEY;

  useEffect(() => {
    // Track pageviews
    if (!pathname || !posthog || isPosthogDisabled) {
      return;
    }
    let url = window.origin + pathname;
    if (searchParams && searchParams.toString()) {
      url = url + `?${searchParams.toString()}`;
    }
    posthog.capture("$pageview", {
      $current_url: url,
      keep_version: process.env.NEXT_PUBLIC_KEEP_VERSION ?? "unknown",
    });
  }, [pathname, searchParams, posthog, isPosthogDisabled]);

  useEffect(() => {
    // Identify user in PostHog
    if (isPosthogDisabled || !session) {
      return;
    }

    const { user } = session;

    const posthog_id = user.email;

    if (posthog_id && posthog_id !== NoAuthUserEmail) {
      console.log("Identifying user in PostHog");
      posthog.identify(posthog_id);
    }
  }, [session, posthog, isPosthogDisabled]);

  return null;
}
