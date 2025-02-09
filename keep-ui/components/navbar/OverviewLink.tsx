"use client";

import { Subtitle } from "@tremor/react";
import { LinkWithIcon } from "components/LinkWithIcon";
import { Disclosure } from "@headlessui/react";
import { IoChevronUp } from "react-icons/io5";
import { LuLayoutDashboard } from "react-icons/lu";
import { Session } from "next-auth";
import clsx from "clsx";

type OverviewLinksProps = { session: Session | null };

export const OverviewLinks = ({ session }: OverviewLinksProps) => {
  return (
    <Disclosure as="div" className="space-y-1" defaultOpen>
      <Disclosure.Button className="w-full flex justify-between items-center p-2">
        {({ open }) => (
          <>
            <Subtitle className="text-xs ml-2 text-gray-900 font-medium uppercase">
              ANALYTICS
            </Subtitle>
            <IoChevronUp
              className={clsx({ "rotate-180": open }, "mr-2 text-slate-400")}
            />
          </>
        )}
      </Disclosure.Button>

      <Disclosure.Panel as="ul" className="space-y-2 p-2 pr-4">
        <li>
          <LinkWithIcon href="/overview" icon={LuLayoutDashboard}>
            <Subtitle>Overview</Subtitle>
          </LinkWithIcon>
        </li>
      </Disclosure.Panel>
    </Disclosure>
  );
};
