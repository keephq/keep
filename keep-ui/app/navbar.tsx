"use client";

import PHProvider from "./posthog-client";
import { SessionProvider } from "next-auth/react";
import NavbarInner from "./navbar-inner";
import { Session } from "next-auth";

const isSingleTenant = process.env.NEXT_PUBLIC_AUTH_ENABLED == "false";

export default function Navbar({ session }: { session: Session | null }) {
  return isSingleTenant ? (
    <PHProvider>
      <NavbarInner user={session?.user} />
    </PHProvider>
  ) : (
    <SessionProvider session={session}>
      <PHProvider>
        <NavbarInner user={session?.user} />
      </PHProvider>
    </SessionProvider>
  );
}
