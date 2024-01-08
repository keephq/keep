"use client";

import PHProvider from "./posthog-provider";
import NavbarInner from "./navbar-inner";
import { useSession } from "next-auth/react";
import { CMDK } from "./command-menu";

export default function Navbar() {
  // extract status and session properties from useSession hook
  const { status, data: session } = useSession();
  // if session is loading, return nothing
  if (status === "loading") return <></>;
  if (status === "unauthenticated") return <></>;
  if (!session) return <></>;


  return (
    <PHProvider>
      <NavbarInner session={session}/>
      <CMDK />
    </PHProvider>
  );
}
