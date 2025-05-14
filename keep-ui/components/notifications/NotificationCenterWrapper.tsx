"use client";

import { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';

// Dynamically import the NotificationCenter component
const NotificationCenter = dynamic(
  () => import('./NotificationCenter').then(mod => ({ default: mod.NotificationCenter })),
  {
    ssr: false,
    loading: () => null
  }
);

export function NotificationCenterWrapper() {
  // Add isClient state to prevent hydration mismatch
  const [isClient, setIsClient] = useState(false);

  // Set isClient to true on component mount
  useEffect(() => {
    setIsClient(true);
  }, []);

  // Only render on the client side
  if (!isClient) {
    return null;
  }

  return <NotificationCenter />;
}
