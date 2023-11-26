"use client";

import PHProvider from "./posthog-provider";
import NavbarInner from "./navbar-inner";
import { useSession } from "next-auth/react";
import { CMDK } from "./command-menu";

export default function Navbar() {
  const { data: session } = useSession();
  return (
    <PHProvider>
      <NavbarInner user={session?.user} />
      <CMDK />
    </PHProvider>
  );
}
