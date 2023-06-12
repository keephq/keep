"use client";

import PHProvider from "./posthog-client";
import NavbarInner from "./navbar-inner";
import { useSession } from "../utils/customAuth";

export default function Navbar() {
  const { data: session } = useSession();
  return (
    <PHProvider>
      <NavbarInner user={session?.user} />
    </PHProvider>
  );
}
