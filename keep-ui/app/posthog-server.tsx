// app/posthog-server.tsx
import { PostHog } from 'posthog-node'
import { cookies } from 'next/headers';
import { v4 as uuidv4 } from 'uuid';

// Extend PostHog to include safeCapture method
interface ExtendedPostHog extends PostHog {
  safeCapture: (event: string, accessToken: any) => void;
}

export default function PostHogClient(): ExtendedPostHog {
  if (!process.env.NEXT_PUBLIC_POSTHOG_KEY) {
    throw new Error('NEXT_PUBLIC_POSTHOG_KEY is not set')
  }
  const posthogClient = new PostHog(process.env.NEXT_PUBLIC_POSTHOG_KEY!, {
    host: process.env.NEXT_PUBLIC_POSTHOG_HOST,
  }) as ExtendedPostHog;

  posthogClient.safeCapture = function(event, accessToken) {
    // Get cookies object
    const nextCookies = cookies();
    // Get anonymousId from cookies
    const anonymousId = nextCookies.get('anonymousId')
    // if there's an access token, use that as the distinctId, else use the anonymousId
    let distinctId = accessToken && accessToken.name ? accessToken.name : anonymousId?.value;
    // If no distinctId is found, generate a new one
    if (!distinctId) {
      console.log("No distinctId found for PostHog event. Generating a new ID.");
      distinctId = uuidv4();
    }
    // Finally, capture the event
    this.capture({
      distinctId: distinctId,
      event: event,
    });
  }

  return posthogClient
}
