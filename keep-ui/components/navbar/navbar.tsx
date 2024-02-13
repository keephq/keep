import InitPostHog from "./init-posthog";
import NavbarInner from "./navbar-inner";

import { CMDK } from "../../app/command-menu";

export default function Navbar() {
  return (
    <>
      <InitPostHog />
      <NavbarInner />
      <CMDK />
    </>
  );
}
