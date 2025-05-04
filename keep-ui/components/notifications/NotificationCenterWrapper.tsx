"use client";

import dynamic from 'next/dynamic';

// Dynamically import the NotificationCenter component
const NotificationCenter = dynamic(
  () => import('./NotificationCenter').then(mod => ({ default: mod.NotificationCenter })),
  { ssr: false }
);

export function NotificationCenterWrapper() {
  return <NotificationCenter />;
}
