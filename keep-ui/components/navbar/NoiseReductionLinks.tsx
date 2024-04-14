"use client";

import { Subtitle } from "@tremor/react";
import { LinkWithIcon } from "components/LinkWithIcon";
import { Mapping, Rules, Workflows, ExportIcon } from "components/icons";
import { Session } from "next-auth";
import { Disclosure } from "@headlessui/react";
import { IoChevronUp } from "react-icons/io5";
import classNames from "classnames";

type NoiseReductionLinksProps = { session: Session | null };

export const NoiseReductionLinks = ({ session }: NoiseReductionLinksProps) => {
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
              NOISE REDUCTION
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

      <Disclosure.Panel as="ul" className="space-y-2 p-2 pr-4">
        <li>
          <LinkWithIcon href="/rules" icon={Rules}>
            Alert Groups
          </LinkWithIcon>
        </li>
        <li>
          <LinkWithIcon href="/workflows" icon={Workflows}>
            Workflows
          </LinkWithIcon>
        </li>
        <li>
          <LinkWithIcon href="/mapping" icon={Mapping}>
            Mapping
          </LinkWithIcon>
        </li>
        <li>
          <LinkWithIcon href="/extraction" icon={ExportIcon}>
            Extraction
          </LinkWithIcon>
        </li>
      </Disclosure.Panel>
    </Disclosure>
  );
};
