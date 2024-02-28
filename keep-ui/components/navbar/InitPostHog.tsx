// took this from https://posthog.com/tutorials/nextjs-app-directory-analytics
"use client";
import posthog from "posthog-js";
import { usePathname, useSearchParams } from "next/navigation";
import { NoAuthUserEmail } from "utils/authenticationType";
import { useConfig } from "utils/hooks/useConfig";
import { Session } from "next-auth";

type InitPostHogProps = {
  session: Session | null;
};

export const InitPostHog = ({ session }: InitPostHogProps) => {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { data: configData } = useConfig();

  if (typeof window !== "undefined" && configData && configData.POSTHOG_KEY) {
    posthog.init(configData.POSTHOG_KEY!, {
      api_host: configData.POSTHOG_HOST,
    });
  }

  if (
    pathname &&
    configData &&
    configData.POSTHOG_KEY &&
    configData.POSTHOG_DISABLED !== "true"
  ) {
    let url = window.origin + pathname;

    if (searchParams) {
      url = url + `?${searchParams.toString()}`;
    }

    if (session) {
      const { user } = session;

      const posthog_id = user.email;

      if (posthog_id && posthog_id !== NoAuthUserEmail) {
        console.log("Identifying user in PostHog");
        posthog.identify(posthog_id);
      }
    }

    posthog.capture("$pageview", {
      $current_url: url,
      keep_version: process.env.NEXT_PUBLIC_KEEP_VERSION ?? "unknown",
    });
  }

  return null;
};
