"use client";

import PHProvider from "./posthog-client";
import { SessionProvider } from "next-auth/react";
import NavbarInner from "./navbar-inner";

const isSingleTenant = process.env.NEXT_PUBLIC_AUTH_ENABLED == "false";

export default function Navbar({ user }: { user: any }) {
  return isSingleTenant ? (
    <PHProvider>
      <NavbarInner user={user} />
    </PHProvider>
  ) : (
    <SessionProvider>
      <PHProvider>
        <NavbarInner user={user} />
      </PHProvider>
    </SessionProvider>
  );
}
