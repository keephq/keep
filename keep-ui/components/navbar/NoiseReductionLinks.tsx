"use client";

import { Subtitle } from "@tremor/react";
import { LinkWithIcon } from "components/LinkWithIcon";
import { Mapping, Rules, Workflows, ExportIcon } from "components/icons";
import { Session } from "next-auth";
import { Disclosure } from "@headlessui/react";
import { IoChevronUp } from "react-icons/io5";
import { TbTopologyRing } from "react-icons/tb";
import { FaVolumeMute } from "react-icons/fa";
import { IoMdGitMerge } from "react-icons/io";
import { useTopology } from "@/app/(keep)/topology/model/useTopology";
import clsx from "clsx";
import { AILink } from "./AILink";

type NoiseReductionLinksProps = { session: Session | null };

export const NoiseReductionLinks = ({ session }: NoiseReductionLinksProps) => {
  const isNOCRole = session?.userRole === "noc";
  const { topologyData } = useTopology();

  if (isNOCRole) {
    return null;
  }

  return (
    <Disclosure as="div" className="space-y-0.5" defaultOpen>
      <Disclosure.Button className="w-full flex justify-between items-center px-2">
        {({ open }) => (
          <>
            <Subtitle className="text-xs ml-2 text-gray-900 font-medium uppercase">
              NOISE REDUCTION
            </Subtitle>
            <IoChevronUp
              className={clsx({ "rotate-180": open }, "mr-2 text-slate-400")}
            />
          </>
        )}
      </Disclosure.Button>

      <Disclosure.Panel as="ul" className="space-y-0.5 p-1 pr-1">
        <li>
          <LinkWithIcon href="/deduplication" icon={IoMdGitMerge}>
            <Subtitle className="text-xs">Deduplication</Subtitle>
          </LinkWithIcon>
        </li>
        <li>
          <LinkWithIcon href="/rules" icon={Rules}>
            <Subtitle className="text-xs">Correlations</Subtitle>
          </LinkWithIcon>
        </li>
        <li>
          <LinkWithIcon href="/workflows" icon={Workflows}>
            <Subtitle className="text-xs">Workflows</Subtitle>
          </LinkWithIcon>
        </li>
        <li>
          <LinkWithIcon
            href="/topology"
            icon={TbTopologyRing}
            isBeta={!topologyData || topologyData.length === 0}
            count={
              topologyData?.length === 0 ? undefined : topologyData?.length
            }
          >
            <Subtitle className="text-xs">Service Topology</Subtitle>
          </LinkWithIcon>
        </li>
        <li>
          <LinkWithIcon href="/mapping" icon={Mapping}>
            <Subtitle className="text-xs">Mapping</Subtitle>
          </LinkWithIcon>
        </li>
        <li>
          <LinkWithIcon href="/extraction" icon={ExportIcon}>
            <Subtitle className="text-xs">Extraction</Subtitle>
          </LinkWithIcon>
        </li>
        <li>
          <LinkWithIcon href="/maintenance" icon={FaVolumeMute}>
            <Subtitle className="text-xs">Maintenance Windows</Subtitle>
          </LinkWithIcon>
        </li>
        <li>
          <AILink></AILink>
        </li>
      </Disclosure.Panel>
    </Disclosure>
  );
};
