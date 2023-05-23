// app/posthog.tsx
// took this from https://posthog.com/tutorials/nextjs-app-directory-analytics
'use client'
import React from 'react';
import posthog from 'posthog-js';
import { PostHogProvider } from 'posthog-js/react';
import { usePathname, useSearchParams } from "next/navigation";
import { useEffect } from "react";
import Cookies from 'js-cookie';
import { useSession } from '../utils/customAuth';



if (typeof window !== 'undefined') {
  posthog.init(process.env.NEXT_PUBLIC_POSTHOG_KEY!, {
    api_host: process.env.NEXT_PUBLIC_POSTHOG_HOST,
  });
  // set anonymousId to cookie
  const anonymousId = posthog.get_distinct_id()
  Cookies.set('anonymousId', anonymousId);
}

interface PHProviderProps {
  children: React.ReactNode;
}

const PHProvider: React.FC<PHProviderProps> = ({ children }) => {
    const pathname = usePathname();
    const searchParams = useSearchParams();
    const { data: session, status, update } = useSession();
    const user = session?.user;
    useEffect(() => {
      const fetchData = () => {

          if (pathname) {
              let url = window.origin + pathname;
              if (searchParams.toString()) {
                  url = url + `?${searchParams.toString()}`;
              }
              const posthog_id = user?.name;
              console.log("PostHog ID: " + posthog_id);
              if(!posthog_id) {
                // TODO: when to reset?
                posthog.reset();
                posthog.identify(posthog_id);
              }
              console.log("Sending pageview event to PostHog");
              posthog.capture(
                  '$pageview',
                  {
                      '$current_url': url,
                  }
              );
              console.log("Event sent to PostHog");
          }
      }
      fetchData();
  }, [pathname, searchParams, session, status]);
    return <PostHogProvider client={posthog}>{children}</PostHogProvider>;
};

export default PHProvider;
