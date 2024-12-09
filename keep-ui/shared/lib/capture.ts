import posthog from "posthog-js";

export const capture = (event: string, properties?: Record<string, any>) => {
  try {
    posthog.capture(event, properties);
  } catch (error) {
    console.error("Error capturing event:", error);
  }
};
