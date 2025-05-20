import posthog from "posthog-js";

/**
 * Safely captures an analytics event with PostHog
 * 
 * This function provides a wrapper around PostHog's capture function with error handling
 * to prevent analytics errors from affecting the application.
 * 
 * @param event - The name of the event to capture
 * @param properties - Optional properties/metadata to include with the event
 * 
 * @example
 * // Capture a simple event
 * capture("button_clicked");
 * 
 * // Capture an event with properties
 * capture("workflow_created", {
 *   workflowId: "123",
 *   workflowType: "alert",
 *   steps: 5
 * });
 */
export const capture = (event: string, properties?: Record<string, any>) => {
  try {
    posthog.capture(event, properties);
  } catch (error) {
    console.error("Error capturing event:", error);
  }
};
