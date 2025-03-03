"use client";

import { Subtitle, Text, Badge } from "@tremor/react";
import { LinkWithIcon } from "components/LinkWithIcon";
import { Disclosure } from "@headlessui/react";
import { IoChevronUp } from "react-icons/io5";
import { LuLayoutDashboard } from "react-icons/lu";
import { Session } from "next-auth";
import clsx from "clsx";
import { useSupersetDashboards } from "@/utils/hooks/useSupersetDashboards";
import { useMounted } from "@/shared/lib/hooks/useMounted";
import { KeepApiError } from "@/shared/api";
import { useConfig } from "@/utils/hooks/useConfig";

type OverviewLinksProps = { session: Session | null };

export const OverviewLinks = ({ session }: OverviewLinksProps) => {
  const isMounted = useMounted();
  const { dashboards, isLoading, error } = useSupersetDashboards();
  const { data: config } = useConfig();

  // if config and not KEEP_SUPERSET_URL, we don't render the menu
  if (config && !config.KEEP_SUPERSET_URL) {
    return null;
  }
  // Don't render the menu at all if there's a KeepApiError
  // which means the backend doesn't work with dashboards
  if (error instanceof KeepApiError) {
    return null;
  }

  if (error) {
    return (
      <Disclosure as="div" className="space-y-1" defaultOpen>
        {({ open }) => (
          <>
            <Disclosure.Button className="w-full flex justify-between items-center p-2">
              <div className="flex items-center relative group">
                <Subtitle className="text-xs ml-2 text-gray-900 font-medium uppercase">
                  ANALYTICS
                </Subtitle>
                <Badge className="ml-2" color="orange" size="xs">
                  BETA
                </Badge>
              </div>
              <IoChevronUp
                className={clsx("mr-2 text-slate-400", {
                  "rotate-180": open,
                })}
              />
            </Disclosure.Button>

            <Disclosure.Panel
              as="ul"
              className="space-y-2 overflow-auto min-w-[max-content] p-2 pr-4"
            >
              <Text className="text-xs max-w-[200px] px-2">
                Dashboards will appear here when saved.
              </Text>
            </Disclosure.Panel>
          </>
        )}
      </Disclosure>
    );
  }

  return (
    <Disclosure as="div" className="space-y-1" defaultOpen>
      {({ open }) => (
        <>
          <Disclosure.Button className="w-full flex justify-between items-center p-2">
            <div className="flex items-center relative group">
              <Subtitle className="text-xs ml-2 text-gray-900 font-medium uppercase">
                ANALYTICS
              </Subtitle>
              <Badge className="ml-2" color="orange" size="xs">
                BETA
              </Badge>
            </div>
            <IoChevronUp
              className={clsx("mr-2 text-slate-400", {
                "rotate-180": open,
              })}
            />
          </Disclosure.Button>

          <Disclosure.Panel
            as="ul"
            className="space-y-2 overflow-auto min-w-[max-content] p-2 pr-4"
          >
            {isMounted && !isLoading && dashboards.length === 0 && (
              <Text className="text-xs max-w-[200px] px-2">
                Dashboards will appear here when saved.
              </Text>
            )}

            {isMounted &&
              !isLoading &&
              dashboards.map((dashboard) => (
                <li key={dashboard.uuid}>
                  <LinkWithIcon
                    href={`/overview/${dashboard.id}`}
                    icon={LuLayoutDashboard}
                  >
                    <Subtitle>{dashboard.title}</Subtitle>
                  </LinkWithIcon>
                </li>
              ))}
          </Disclosure.Panel>
        </>
      )}
    </Disclosure>
  );
};
