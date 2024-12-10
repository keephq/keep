"use client";

import { Menu } from "@headlessui/react";
import { LinkWithIcon } from "components/LinkWithIcon";
import { Session } from "next-auth";
import { useConfig } from "utils/hooks/useConfig";
import { AuthType } from "@/utils/authenticationType";
import Link from "next/link";
import { AiOutlineRight } from "react-icons/ai";
import { VscDebugDisconnect } from "react-icons/vsc";
import { useFloating } from "@floating-ui/react";
import { Icon, Subtitle } from "@tremor/react";
import UserAvatar from "./UserAvatar";
import * as Frigade from "@frigade/react";
import { useState } from "react";
import Onboarding from "./Onboarding";
import { useSignOut } from "@/shared/lib/hooks/useSignOut";
import { FaSlack } from "react-icons/fa";
import { ThemeControl } from "@/shared/ui/theme/ThemeControl";
import { HiOutlineDocumentText } from "react-icons/hi2";

const ONBOARDING_FLOW_ID = "flow_FHDz1hit";

type UserDropdownProps = {
  session: Session;
};

const UserDropdown = ({ session }: UserDropdownProps) => {
  const { userRole, user } = session;
  const { name, image, email } = user;

  const { data: configData } = useConfig();
  const signOut = useSignOut();
  const { refs, floatingStyles } = useFloating({
    placement: "right-end",
    strategy: "fixed",
  });

  const isNoAuth = configData?.AUTH_TYPE === AuthType.NOAUTH;
  return (
    <Menu as="li" ref={refs.setReference} className="w-full">
      <Menu.Button className="flex items-center justify-between w-full text-sm pl-2.5 pr-2 py-1 text-gray-700 hover:bg-stone-200/50 font-medium rounded-lg hover:text-orange-400 focus:ring focus:ring-orange-300 group capitalize">
        <span className="space-x-3 flex items-center w-full">
          <UserAvatar image={image} name={name ?? email} />{" "}
          <Subtitle className="truncate">{name ?? email}</Subtitle>
        </span>
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
          {!isNoAuth && (
            <li>
              <Menu.Item
                as="button"
                className="ui-active:bg-orange-400 ui-active:text-white ui-not-active:text-gray-900 group flex w-full items-center rounded-md px-2 py-2 text-sm"
                onClick={signOut}
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
  const { flow } = Frigade.useFlow(ONBOARDING_FLOW_ID);
  const [isOnboardingOpen, setIsOnboardingOpen] = useState(false);

  return (
    <>
      <ul className="space-y-2 p-2">
        {flow?.isCompleted === false && (
          <li>
            <Frigade.ProgressBadge
              flowId={ONBOARDING_FLOW_ID}
              onClick={() => setIsOnboardingOpen(true)}
            />
            <Onboarding
              isOpen={isOnboardingOpen}
              toggle={() => setIsOnboardingOpen(false)}
              variables={{
                name: session?.user.name ?? session?.user.email,
              }}
            />
          </li>
        )}
        <li>
          <LinkWithIcon href="/providers" icon={VscDebugDisconnect}>
            Providers
          </LinkWithIcon>
        </li>
        <li className="flex items-center gap-2">
          <LinkWithIcon
            icon={FaSlack}
            href="https://slack.keephq.dev/"
            className="w-auto pr-3.5"
            target="_blank"
          >
            Join Slack
          </LinkWithIcon>
          <LinkWithIcon
            icon={HiOutlineDocumentText}
            iconClassName="w-4"
            href="https://docs.keephq.dev/"
            className="w-auto px-3.5"
            target="_blank"
          >
            Docs
          </LinkWithIcon>
        </li>
        <div className="flex items-center justify-between">
          {session && <UserDropdown session={session} />}
          <ThemeControl className="text-sm size-10 flex items-center justify-center font-medium rounded-lg focus:ring focus:ring-orange-300 hover:!bg-stone-200/50" />
        </div>
      </ul>
    </>
  );
};
