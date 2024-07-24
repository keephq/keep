"use client";

import { usePathname } from "next/navigation";
import { Subtitle } from "@tremor/react";
import { LinkWithIcon } from "components/LinkWithIcon";
import { DoorbellNotification } from "components/icons";
import { Session } from "next-auth";
import { Disclosure } from "@headlessui/react";
import { IoChevronUp } from "react-icons/io5";
import classNames from "classnames";
import { useIncidents } from "utils/hooks/useIncidents";
import { MdNearbyError } from "react-icons/md";

type IncidentsLinksProps = { session: Session | null };
const SHOW_N_INCIDENTS = 3;

export const IncidentsLinks = ({ session }: IncidentsLinksProps) => {
  const isNOCRole = session?.userRole === "noc";
  const { data: incidents } = useIncidents();
  const currentPath = usePathname();

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
              className={classNames(
                { "rotate-180": open },
                "mr-2 text-slate-400"
              )}
            />
          </>
        )}
      </Disclosure.Button>

      <Disclosure.Panel as="ul" className="space-y-2 p-2 pr-4 relative">
        <li className="relative">
          <LinkWithIcon
            href="/incidents"
            icon={DoorbellNotification}
            count={incidents?.count}
          >
            <Subtitle>Incidents</Subtitle>
          </LinkWithIcon>
        </li>
        {incidents?.items.slice(0, SHOW_N_INCIDENTS).map((incident) => (
          <li key={incident.id} className="relative pl-8">
            <LinkWithIcon
              href={`/incidents/${incident.id}`}
              icon={MdNearbyError}
              count={incident.number_of_alerts ?? 0}
              className={classNames("block p-2 rounded-none border-l-2", {
                "bg-gray-200": currentPath === `/incidents/${incident.id}`,
              })}
            >

              <Subtitle className="text-sm max-w-[7.7rem]">{incident.name}</Subtitle>
            </LinkWithIcon>
          </li>
        ))}
        {/* {incidents && incidents.items.length > SHOW_N_INCIDENTS && (
          <li className="relative pl-8">
            <div className="block p-2 text-gray-500">...</div>
          </li>
        )} */}
      </Disclosure.Panel>
    </Disclosure>
  );
};
