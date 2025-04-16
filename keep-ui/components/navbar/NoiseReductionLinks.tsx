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
import { useConfig } from "@/utils/hooks/useConfig";
import { useTenantConfiguration } from "@/utils/hooks/useTenantConfiguration";
import { ReactNode } from "react";
import Skeleton from "react-loading-skeleton";
import "react-loading-skeleton/dist/skeleton.css";

type NoiseReductionLinksProps = { session: Session | null };

type TogglableLinkProps = {
  disabledConfigKey: string;
  children: ReactNode;
};

const TogglableLink = ({ children, disabledConfigKey }: TogglableLinkProps) => {
  const { data: tenantConfig, isLoading } = useTenantConfiguration();

  if (isLoading || !tenantConfig) {
    return (
      <div className="flex gap-2 items-center h-7 pl-3">
        <Skeleton className="min-h-5 min-w-5" />
        <Skeleton
          className="min-h-5 min-w-24"
          containerClassName="min-h-5 min-w-24"
        />
      </div>
    );
  }

  if (!tenantConfig?.[disabledConfigKey]) {
    return <>{children}</>;
  }
};

export const NoiseReductionLinks = ({ session }: NoiseReductionLinksProps) => {
  const isNOCRole = session?.userRole === "noc";
  const { topologyData } = useTopology();
  const { data: tenantConfig, isLoading } = useTenantConfiguration();
  const noiseReductionKeys = {
    HIDE_NAVBAR_DEDUPLICATION: "HIDE_NAVBAR_DEDUPLICATION",
    HIDE_NAVBAR_CORRELATION: "HIDE_NAVBAR_CORRELATION",
    HIDE_NAVBAR_WORKFLOWS: "HIDE_NAVBAR_WORKFLOWS",
    HIDE_NAVBAR_SERVICE_TOPOLOGY: "HIDE_NAVBAR_SERVICE_TOPOLOGY",
    HIDE_NAVBAR_MAPPING: "HIDE_NAVBAR_MAPPING",
    HIDE_NAVBAR_EXTRACTION: "HIDE_NAVBAR_EXTRACTION",
    HIDE_NAVBAR_MAINTENANCE_WINDOW: "HIDE_NAVBAR_MAINTENANCE_WINDOW",
    HIDE_NAVBAR_AI_PLUGINS: "HIDE_NAVBAR_AI_PLUGINS",
  };

  if (isNOCRole) {
    return null;
  }

  if (!Object.values(noiseReductionKeys).some((key) => !tenantConfig?.[key])) {
    return null;
  }

  return (
    <Disclosure as="div" className="space-y-0.5" defaultOpen>
      <Disclosure.Button className="w-full flex justify-between items-center px-2">
        {({ open }) => (
          <>
            {tenantConfig && (
              <>
                <Subtitle className="text-xs ml-2 text-gray-900 font-medium uppercase">
                  NOISE REDUCTION
                </Subtitle>
                <IoChevronUp
                  className={clsx(
                    { "rotate-180": open },
                    "mr-2 text-slate-400"
                  )}
                />
              </>
            )}
            {!tenantConfig && (
              <div className="flex items-center h-7 pl-2">
                <Skeleton className="min-h-5 min-w-36" />
              </div>
            )}
          </>
        )}
      </Disclosure.Button>

      <Disclosure.Panel as="ul" className="space-y-0.5 p-1 pr-1">
        <TogglableLink
          disabledConfigKey={noiseReductionKeys.HIDE_NAVBAR_DEDUPLICATION}
        >
          <li>
            <LinkWithIcon href="/deduplication" icon={IoMdGitMerge}>
              <Subtitle className="text-xs">Deduplication</Subtitle>
            </LinkWithIcon>
          </li>
        </TogglableLink>
        <TogglableLink disabledConfigKey="HIDE_NAVBAR_CORRELATION">
          <li>
            <LinkWithIcon href="/rules" icon={Rules}>
              <Subtitle className="text-xs">Correlations</Subtitle>
            </LinkWithIcon>
          </li>
        </TogglableLink>
        <TogglableLink
          disabledConfigKey={noiseReductionKeys.HIDE_NAVBAR_WORKFLOWS}
        >
          <li>
            <LinkWithIcon href="/workflows" icon={Workflows}>
              <Subtitle className="text-xs">Workflows</Subtitle>
            </LinkWithIcon>
          </li>
        </TogglableLink>

        <TogglableLink
          disabledConfigKey={noiseReductionKeys.HIDE_NAVBAR_SERVICE_TOPOLOGY}
        >
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
        </TogglableLink>
        <TogglableLink
          disabledConfigKey={noiseReductionKeys.HIDE_NAVBAR_MAPPING}
        >
          <li>
            <LinkWithIcon href="/mapping" icon={Mapping}>
              <Subtitle className="text-xs">Mapping</Subtitle>
            </LinkWithIcon>
          </li>
        </TogglableLink>
        <TogglableLink
          disabledConfigKey={noiseReductionKeys.HIDE_NAVBAR_EXTRACTION}
        >
          <li>
            <LinkWithIcon href="/extraction" icon={ExportIcon}>
              <Subtitle className="text-xs">Extraction</Subtitle>
            </LinkWithIcon>
          </li>
        </TogglableLink>
        <TogglableLink
          disabledConfigKey={noiseReductionKeys.HIDE_NAVBAR_MAINTENANCE_WINDOW}
        >
          <li>
            <LinkWithIcon href="/maintenance" icon={FaVolumeMute}>
              <Subtitle className="text-xs">Maintenance Windows</Subtitle>
            </LinkWithIcon>
          </li>
        </TogglableLink>
        <TogglableLink
          disabledConfigKey={noiseReductionKeys.HIDE_NAVBAR_AI_PLUGINS}
        >
          <li>
            <AILink></AILink>
          </li>
        </TogglableLink>
      </Disclosure.Panel>
    </Disclosure>
  );
};
