"use client";

import { useEffect, useState } from "react";
import { useMentionNotifications } from "@/utils/hooks/useMentionNotifications";

/**
 * Provider component that sets up mention notifications
 * This is a client component that doesn't render anything visible
 */
export function MentionNotificationsProvider() {
  // Add isClient state to prevent hydration mismatch
  const [isClient, setIsClient] = useState(false);

  // Set isClient to true on component mount
  useEffect(() => {
    setIsClient(true);
  }, []);

  // Use the hook directly - it has its own isClient check
  useMentionNotifications();

  return null;
}
