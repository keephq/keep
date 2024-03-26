"use client";

import { Subtitle } from "@tremor/react";
import { LinkWithIcon } from "components/LinkWithIcon";
import { MdOutlineEngineering } from "react-icons/md";
import { LuWorkflow } from "react-icons/lu";
import { RiMindMap } from "react-icons/ri";
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
          <LinkWithIcon href="/rules" icon={MdOutlineEngineering}>
            Correlations
          </LinkWithIcon>
        </li>
        <li>
          <LinkWithIcon href="/workflows" icon={LuWorkflow}>
            Workflows
          </LinkWithIcon>
        </li>
        <li>
          <LinkWithIcon href="/mapping" icon={RiMindMap}>
            Mapping
          </LinkWithIcon>
        </li>
      </Disclosure.Panel>
    </Disclosure>
  );
};
