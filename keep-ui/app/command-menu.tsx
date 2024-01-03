"use client";

import { Command } from "cmdk";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  GitHubLogoIcon,
  FileTextIcon,
  TwitterLogoIcon,
} from "@radix-ui/react-icons";
import {
  GlobeAltIcon,
  UserGroupIcon,
  EnvelopeIcon,
  KeyIcon,
} from "@heroicons/react/24/outline";
import { VscDebugDisconnect } from "react-icons/vsc";
import { LuWorkflow } from "react-icons/lu";
import { AiOutlineAlert } from "react-icons/ai";
import { MdOutlineEngineering } from "react-icons/md";

import "../styles/linear.scss";

export function CMDK() {
  const [open, setOpen] = useState(false);
  const router = useRouter();

  // Toggle the menu when ⌘K is pressed
  useEffect(() => {
    const down = (e: any) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((open) => !open);
      }
    };

    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, []);
  return (
    <div className="linear">
      <Command.Dialog open={open} onOpenChange={setOpen}>
        <div cmdk-linear-badge="">Keep Command Palette</div>
        <Command.Input autoFocus placeholder="Type a command or search..." />
        <Command.Group heading="Navigate" className="w-full">
          <Command.List className="w-full">
            <Command.Empty>No results found.</Command.Empty>
            {navigationItems.map(({ icon, label, shortcut, navigate }) => {
              return (
                <Command.Item
                  className="w-full"
                  key={label}
                  value={label}
                  onSelect={() => {
                    setOpen((open) => !open);
                    router.push(navigate!);
                  }}
                >
                  {icon}
                  {label}
                  <div cmdk-linear-shortcuts="">
                    {shortcut.map((key) => {
                      return <kbd key={key}>{key}</kbd>;
                    })}
                  </div>
                </Command.Item>
              );
            })}
          </Command.List>
        </Command.Group>
        <Command.Group heading="External sources">
          <Command.List>
            {externalItems.map(({ icon, label, shortcut, navigate }) => {
              return (
                <Command.Item
                  key={label}
                  value={label}
                  onSelect={() => {
                    setOpen((open) => !open);
                    window.open(navigate, "_blank");
                  }}
                >
                  {icon}
                  {label}
                  <div cmdk-linear-shortcuts="">
                    {shortcut.map((key) => {
                      return <kbd key={key}>{key}</kbd>;
                    })}
                  </div>
                </Command.Item>
              );
            })}
          </Command.List>
        </Command.Group>
      </Command.Dialog>
    </div>
  );
}

const navigationItems = [
  {
    icon: <VscDebugDisconnect />,
    label: "Go to the providers page",
    shortcut: ["p"],
    navigate: "/providers",
  },
  {
    icon: <AiOutlineAlert />,
    label: "Go to alert console",
    shortcut: ["g"],
    navigate: "/alerts",
  },
  {
    icon: <MdOutlineEngineering />,
    label: "Go to alert groups",
    shortcut: ["g"],
    navigate: "/rules",
  },
  {
    icon: <LuWorkflow />,
    label: "Go to the workflows page",
    shortcut: ["wf"],
    navigate: "/workflows",
  },
  {
    icon: <UserGroupIcon />,
    label: "Go to users management",
    shortcut: ["u"],
    navigate: "/settings?selectedTab=users",
  },
  {
    icon: <GlobeAltIcon />,
    label: "Go to generic webhook",
    shortcut: ["w"],
    navigate: "/settings?selectedTab=webhook",
  },
  {
    icon: <EnvelopeIcon />,
    label: "Go to SMTP settings",
    shortcut: ["s"],
    navigate: "/settings?selectedTab=smtp",
  },
  {
    icon: <KeyIcon />,
    label: "Go to API key",
    shortcut: ["a"],
    navigate: "/settings?selectedTab=api-key",
  },
];

const externalItems = [
  {
    icon: <FileTextIcon />,
    label: "Keep Docs",
    shortcut: ["⇧", "D"],
    navigate: "https://docs.keephq.dev",
  },
  {
    icon: <GitHubLogoIcon />,
    label: "Keep Source code",
    shortcut: ["⇧", "C"],
    navigate: "https://github.com/keephq/keep",
  },
  {
    icon: <TwitterLogoIcon />,
    label: "Keep Twitter",
    shortcut: ["⇧", "T"],
    navigate: "https://twitter.com/keepalerting",
  },
];
