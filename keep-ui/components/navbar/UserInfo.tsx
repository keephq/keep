"use client";

import { Menu } from "@headlessui/react";
import { LinkWithIcon } from "components/LinkWithIcon";
import { Session } from "next-auth";
import { signOut } from "next-auth/react";
import { useConfig } from "utils/hooks/useConfig";
import { AuthenticationType } from "utils/authenticationType";
import Image from "next/image";
import Link from "next/link";
import { LuSlack } from "react-icons/lu";
import { AiOutlineRight } from "react-icons/ai";
import { VscDebugDisconnect } from "react-icons/vsc";
import DarkModeToggle from "app/dark-mode-toggle";
import { useFloating } from "@floating-ui/react";
import { Icon, Subtitle } from "@tremor/react";
import UserAvatar from "./UserAvatar";

type UserDropdownProps = {
  session: Session;
};

const UserDropdown = ({ session }: UserDropdownProps) => {
  const { userRole, user } = session;
  const { name, image, email } = user;

  const { data: configData } = useConfig();
  const { refs, floatingStyles } = useFloating({
    placement: "right-end",
    strategy: "fixed",
  });

  return (
    <Menu as="li" ref={refs.setReference}>
      <Menu.Button className="flex items-center justify-between w-full text-sm pl-2.5 pr-2 py-1 text-gray-700 hover:bg-stone-200/50 font-medium rounded-lg hover:text-orange-400 focus:ring focus:ring-orange-300 group capitalize">
        <span className="space-x-3 flex items-center w-full">
          <UserAvatar image={image} name={name ?? email} />{" "}
          <Subtitle className="truncate">{name ?? email}</Subtitle>
        </span>

        <Icon
          className="text-gray-700 font-medium px-0"
          size="xs"
          icon={AiOutlineRight}
        />
      </Menu.Button>

      <Menu.Items
        className="w-48 ml-2 origin-right divide-y divide-gray-100 rounded-md bg-white shadow-lg ring-1 ring-black/5 focus:outline-none z-10"
        style={floatingStyles}
        ref={refs.setFloating}
        as="ul"
      >
        <div className="px-1 py-1 ">
          {userRole !== "noc" && (
            <li>
              <Menu.Item
                as={Link}
                href="/settings"
                className="ui-active:bg-orange-400 ui-active:text-white ui-not-active:text-gray-900 group flex w-full items-center rounded-md px-2 py-2 text-sm"
              >
                Settings
              </Menu.Item>
            </li>
          )}
          {configData?.AUTH_TYPE !== AuthenticationType.NOAUTH && (
            <li>
              <Menu.Item
                as="button"
                className="ui-active:bg-orange-400 ui-active:text-white ui-not-active:text-gray-900 group flex w-full items-center rounded-md px-2 py-2 text-sm"
                onClick={() => signOut()}
              >
                Sign out
              </Menu.Item>
            </li>
          )}
        </div>
      </Menu.Items>
    </Menu>
  );
};

type UserInfoProps = {
  session: Session | null;
};

export const UserInfo = ({ session }: UserInfoProps) => {
  return (
    <ul className="space-y-2 p-2">
      <li>
        <LinkWithIcon href="/providers" icon={VscDebugDisconnect}>
          Providers
        </LinkWithIcon>
      </li>
      <li>
        {/* TODO: slows everything down. needs to be replaced */}
        <DarkModeToggle />
      </li>
      <li>
        <LinkWithIcon
          icon={LuSlack}
          href="https://slack.keephq.dev/"
          target="_blank"
        >
          Join our Slack
        </LinkWithIcon>
      </li>

      {session && <UserDropdown session={session} />}
    </ul>
  );
};
