import InitPostHog from "./init-posthog";
import NavbarInner from "./navbar-inner";

import { CMDK } from "./command-menu";

export default function Navbar() {
  return (
    <>
      <InitPostHog />
      <NavbarInner />
      <CMDK />
    </>
  );
}
