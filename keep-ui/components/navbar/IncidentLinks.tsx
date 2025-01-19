"use client";

import { usePathname } from "next/navigation";
import { Subtitle } from "@tremor/react";
import { LinkWithIcon } from "components/LinkWithIcon";
import { Session } from "next-auth";
import { Disclosure } from "@headlessui/react";
import { IoChevronUp } from "react-icons/io5";
import { useIncidents, usePollIncidents } from "utils/hooks/useIncidents";
import { MdFlashOn } from "react-icons/md";
import clsx from "clsx";

type IncidentsLinksProps = { session: Session | null };

export const IncidentsLinks = ({ session }: IncidentsLinksProps) => {
  const isNOCRole = session?.userRole === "noc";
  const { data: incidents, mutate } = useIncidents(
    true,
    25,
    0,
    { id: "creation_time", desc: false },
    {}
  );
  usePollIncidents(mutate);

  if (isNOCRole) {
    return null;
  }

  return (
    <Disclosure as="div" className="space-y-1" defaultOpen>
      <Disclosure.Button className="w-full flex justify-between items-center p-2">
        {({ open }) => (
          <>
            <Subtitle className="text-xs ml-2 text-gray-900 font-medium uppercase">
              INCIDENTS
            </Subtitle>
            <IoChevronUp
              className={clsx({ "rotate-180": open }, "mr-2 text-slate-400")}
            />
          </>
        )}
      </Disclosure.Button>

      <Disclosure.Panel as="ul" className="space-y-2 p-2 pr-4 relative">
        <li className="relative">
          <LinkWithIcon
            href="/incidents"
            icon={MdFlashOn}
            count={incidents?.count}
          >
            <Subtitle>Incidents</Subtitle>
          </LinkWithIcon>
        </li>
      </Disclosure.Panel>
    </Disclosure>
  );
};
