"use client";
import { Disclosure, Menu, Transition } from "@headlessui/react";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { signOut, useSession } from "next-auth/react";
import { Fragment, useState } from "react";
import {
  Bars3Icon,
  DocumentTextIcon,
  XMarkIcon,
} from "@heroicons/react/24/outline";
import { VscDebugDisconnect } from "react-icons/vsc";
import { LuWorkflow } from "react-icons/lu";
import { AiOutlineAlert } from "react-icons/ai";
import { MdOutlineEngineering } from "react-icons/md";

import Link from "next/link";
import { Icon } from "@tremor/react";
import { AuthenticationType } from "utils/authenticationType";
import useSWR from "swr";
import { fetcher } from "utils/fetcher";
import { User } from "next-auth";
import { InternalConfig } from "types/internal-config";
import { NameInitialsAvatar } from "react-name-initials-avatar";
import DarkModeToggle from "../../app/dark-mode-toggle";
import { useConfig } from "utils/hooks/useConfig";

const navigation = [
  { name: "Providers", href: "/providers", icon: VscDebugDisconnect },
  { name: "Alerts", href: "/alerts", icon: AiOutlineAlert },
  { name: "Alert Groups", href: "/rules", icon: MdOutlineEngineering },
  { name: "Workflows", href: "/workflows", icon: LuWorkflow },
];

// noc navigation incldues only alerts
const nocNavigation = [
  { name: "Alerts", href: "/alerts", icon: AiOutlineAlert },
];

function classNames(...classes: string[]) {
  return classes.filter(Boolean).join(" ");
}

const SlackLogo = (props: any) => (
  <svg
    width="800px"
    height="800px"
    viewBox="0 0 16 16"
    xmlns="http://www.w3.org/2000/svg"
    fill="none"
    {...props}
  >
    <g fillRule="evenodd" clipRule="evenodd">
      <path
        fill="#E01E5A"
        d="M2.471 11.318a1.474 1.474 0 001.47-1.471v-1.47h-1.47A1.474 1.474 0 001 9.846c.001.811.659 1.469 1.47 1.47zm3.682-2.942a1.474 1.474 0 00-1.47 1.471v3.683c.002.811.66 1.468 1.47 1.47a1.474 1.474 0 001.47-1.47V9.846a1.474 1.474 0 00-1.47-1.47z"
      />
      <path
        fill="#36C5F0"
        d="M4.683 2.471c.001.811.659 1.469 1.47 1.47h1.47v-1.47A1.474 1.474 0 006.154 1a1.474 1.474 0 00-1.47 1.47zm2.94 3.682a1.474 1.474 0 00-1.47-1.47H2.47A1.474 1.474 0 001 6.153c.002.812.66 1.469 1.47 1.47h3.684a1.474 1.474 0 001.47-1.47z"
      />
      <path
        fill="#2EB67D"
        d="M9.847 7.624a1.474 1.474 0 001.47-1.47V2.47A1.474 1.474 0 009.848 1a1.474 1.474 0 00-1.47 1.47v3.684c.002.81.659 1.468 1.47 1.47zm3.682-2.941a1.474 1.474 0 00-1.47 1.47v1.47h1.47A1.474 1.474 0 0015 6.154a1.474 1.474 0 00-1.47-1.47z"
      />
      <path
        fill="#ECB22E"
        d="M8.377 9.847c.002.811.659 1.469 1.47 1.47h3.683A1.474 1.474 0 0015 9.848a1.474 1.474 0 00-1.47-1.47H9.847a1.474 1.474 0 00-1.47 1.47zm2.94 3.682a1.474 1.474 0 00-1.47-1.47h-1.47v1.47c.002.812.659 1.469 1.47 1.47a1.474 1.474 0 001.47-1.47z"
      />
    </g>
  </svg>
);

const GnipLogo = (props: any) => (
  <svg
    width="24px"
    height="24px"
    viewBox="0 0 24 24"
    xmlns="http://www.w3.org/2000/svg"
    fill="none"
    {...props}
  >
    {" "}
    <image id="image0" width={"24"} height={"24"} href="/gnip.webp" />
  </svg>
);

export default function NavbarInner() {
  return <nav className="bg-gray-50 col-span-1"></nav>;
}
