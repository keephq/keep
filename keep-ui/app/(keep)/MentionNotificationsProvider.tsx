"use client";

import { useMentionNotifications } from "@/utils/hooks/useMentionNotifications";

export function MentionNotificationsProvider() {
  // This component doesn't render anything, it just sets up the notifications
  useMentionNotifications();
  return null;
}
