"use client";

import { Subtitle } from "@tremor/react";
import { LinkWithIcon } from "components/LinkWithIcon";
import { Workflows } from "components/icons";
import { Session } from "next-auth";
import { Disclosure } from "@headlessui/react";
import { IoChevronUp } from "react-icons/io5";
import clsx from "clsx";

type AutomationLinksProps = { session: Session | null };

export const AutomationLinks = ({ session }: AutomationLinksProps) => {
  const isNOCRole = session?.userRole === "noc";

  if (isNOCRole) {
    return null;
  }

  return (
    <Disclosure as="div" className="space-y-1" defaultOpen>
      <Disclosure.Button className="w-full flex justify-between items-center p-2">
        {({ open }) => (
          <>
            <Subtitle className="text-xs ml-2 text-gray-900 font-medium uppercase">
              AUTOMATION
            </Subtitle>
            <IoChevronUp
              className={clsx({ "rotate-180": open }, "mr-2 text-slate-400")}
            />
          </>
        )}
      </Disclosure.Button>

      <Disclosure.Panel as="ul" className="space-y-2 p-2 pr-4">
        <li>
          <LinkWithIcon href="/workflows" icon={Workflows}>
            <Subtitle>Workflows</Subtitle>
          </LinkWithIcon>
        </li>
      </Disclosure.Panel>
    </Disclosure>
  );
};
