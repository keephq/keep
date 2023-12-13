// app/posthog.tsx
// took this from https://posthog.com/tutorials/nextjs-app-directory-analytics
"use client";
import React from "react";
import posthog from "posthog-js";
import { PostHogProvider } from "posthog-js/react";
import { usePathname, useSearchParams } from "next/navigation";
import { useEffect } from "react";
import { useSession } from "next-auth/react";
import { NoAuthUserEmail } from "utils/authenticationType";

if (typeof window !== "undefined" && process.env.NEXT_PUBLIC_POSTHOG_KEY) {
  posthog.init(process.env.NEXT_PUBLIC_POSTHOG_KEY!, {
    api_host: process.env.NEXT_PUBLIC_POSTHOG_HOST,
  });
}

interface PHProviderProps {
  children: React.ReactNode;
}

const PHProvider: React.FC<PHProviderProps> = ({ children }) => {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { data: session } = useSession();
  useEffect(() => {
    const user = session?.user;
    const fetchData = () => {
      if (
        pathname &&
        process.env.NEXT_PUBLIC_POSTHOG_KEY &&
        process.env.POSTHOG_DISABLED !== "true" &&
        process.env.NEXT_PUBLIC_POSTHOG_DISABLED !== "true"
      ) {
        let url = window.origin + pathname;
        if (searchParams?.toString()) {
          url = url + `?${searchParams.toString()}`;
        }
        const posthog_id = user?.email;
        if (posthog_id && posthog_id !== NoAuthUserEmail) {
          console.log("Identifying user in PostHog");
          posthog.identify(posthog_id);
        }
        posthog.capture("$pageview", {
          $current_url: url,
          keep_version: process.env.NEXT_PUBLIC_KEEP_VERSION,
        });
      }
    };
    fetchData();
  }, [pathname, searchParams, session]);
  return <PostHogProvider client={posthog}>{children}</PostHogProvider>;
};

export default PHProvider;
