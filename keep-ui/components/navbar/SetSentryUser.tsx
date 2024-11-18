"use client";

import { Session } from "next-auth";
import { useSetSentryUser } from "@/shared/lib/useSetSentryUser";

export function SetSentryUser({ session }: { session: Session | null }) {
  useSetSentryUser({ session });
  return null;
}
