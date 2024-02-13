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
import { Search } from "./search";
import { ConfigureLinks } from "./ConfigureLInks";
import { MonitorLinks } from "./MonitorLinks";
import { AnalyzeLinks } from "./AnalyzeLinks";
import { LearnLinks } from "./LearnLinks";
import { UserInfo } from "./UserInfo";

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

export default function NavbarInner() {
  return (
    <aside className="bg-gray-50 col-span-1">
      <nav className="flex flex-col">
        <div className="flex-1">
          <Search />
          <ConfigureLinks />
          <MonitorLinks />
          <AnalyzeLinks />
          <LearnLinks />
        </div>

        <UserInfo />
      </nav>
    </aside>
  );
}
