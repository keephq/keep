import * as Sentry from "@sentry/nextjs";
import { Session } from "next-auth";

export function setSentryUserServer(session: Session | null) {
  if (process.env.SENTRY_DISABLED === "true") {
    return;
  }

  if (!session || !session.user) {
    return;
  }

  Sentry.setUser(session.user);
}
