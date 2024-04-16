"use client";

import { Subtitle } from "@tremor/react";

import { LinkWithIcon } from "components/LinkWithIcon";
import { CustomPresetAlertLinks } from "components/navbar/CustomPresetAlertLinks";
import {
  DoorbellNotification,
  SilencedDoorbellNotification,
  Trashcan,
} from "components/icons";
import { IoChevronUp } from "react-icons/io5";
import { AiOutlineGroup } from "react-icons/ai";
import { Disclosure } from "@headlessui/react";
import classNames from "classnames";
import { Session } from "next-auth";

type AlertsLinksProps = {
  session: Session | null;
};

export const AlertsLinks = ({ session }: AlertsLinksProps) => {
  return (
    <Disclosure as="div" className="space-y-1" defaultOpen>
      <Disclosure.Button className="w-full flex justify-between items-center p-2">
        {({ open }) => (
          <>
            <Subtitle className="text-xs ml-2 text-gray-900 font-medium uppercase">
              ALERTS
            </Subtitle>
            <IoChevronUp
              className={classNames(
                { "rotate-180": open },
                "mr-2 text-slate-400"
              )}
            />
          </>
        )}
      </Disclosure.Button>
      <Disclosure.Panel
        as="ul"
        className="space-y-2 overflow-auto min-w-[max-content] p-2 pr-4"
      >
        <li>
          <LinkWithIcon href="/alerts/feed" icon={DoorbellNotification}>
            Feed [All]
          </LinkWithIcon>
        </li>
        {session && <CustomPresetAlertLinks session={session} />}
        <li>
          <LinkWithIcon href="/alerts/groups" icon={AiOutlineGroup}>
            Correlation
          </LinkWithIcon>
        </li>
        <li>
          <LinkWithIcon
            href="/alerts/dismissed"
            icon={SilencedDoorbellNotification}
          >
            Dismissed
          </LinkWithIcon>
        </li>
        <li>
          <LinkWithIcon href="/alerts/deleted" icon={Trashcan}>
            Deleted
          </LinkWithIcon>
        </li>
      </Disclosure.Panel>
    </Disclosure>
  );
};
