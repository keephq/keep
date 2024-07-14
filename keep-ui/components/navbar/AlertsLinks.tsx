"use client";

import { Badge, Subtitle } from "@tremor/react";

import { LinkWithIcon } from "components/LinkWithIcon";
import { CustomPresetAlertLinks } from "components/navbar/CustomPresetAlertLinks";
import { SilencedDoorbellNotification, Trashcan } from "components/icons";
import { IoChevronUp } from "react-icons/io5";
import { AiOutlineGroup, AiOutlineSound, AiOutlineSwap } from "react-icons/ai";
import { Disclosure } from "@headlessui/react";
import classNames from "classnames";
import { Session } from "next-auth";
import { usePresets } from "utils/hooks/usePresets";
import { useEffect, useState } from "react";

type AlertsLinksProps = {
  session: Session | null;
};

export const AlertsLinks = ({ session }: AlertsLinksProps) => {
  const { useStaticPresets, staticPresetsOrderFromLS } = usePresets();
  // Fetch static presets; initially fallback to local storage
  const { data: fetchedPresets = [] } = useStaticPresets({
    revalidateIfStale: false,
  });

  // Determine whether to use fetched presets or fall back to local storage
  const [staticPresets, setStaticPresets] = useState(staticPresetsOrderFromLS);

  useEffect(() => {
    // Convert both arrays to string to perform a comparison
    if (
      fetchedPresets.length > 0 &&
      JSON.stringify(staticPresets) !== JSON.stringify(staticPresetsOrderFromLS)
    ) {
      setStaticPresets(staticPresetsOrderFromLS);
    }
  }, [fetchedPresets]);

  const mainPreset = staticPresets.find((preset) => preset.name === "feed");
  const dismissedPreset = staticPresets.find(
    (preset) => preset.name === "dismissed"
  );
  const groupsPreset = staticPresets.find((preset) => preset.name === "groups");

  return (
    <>
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
                  "mr-2 text-slate-400 transition-transform duration-300 ease-in-out"
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
            <LinkWithIcon
              href="/alerts/feed"
              icon={AiOutlineSwap}
              count={mainPreset?.alerts_count}
            >
              <Subtitle>Feed</Subtitle>
            </LinkWithIcon>
          </li>
          {session && <CustomPresetAlertLinks session={session} />}
          <li>
            <LinkWithIcon
              href="/alerts/groups"
              icon={AiOutlineGroup}
              count={groupsPreset?.alerts_count}
            >
              <Subtitle>
              Correlation
              </Subtitle>

            </LinkWithIcon>
          </li>
          <li>
            <LinkWithIcon
              href="/alerts/dismissed"
              icon={SilencedDoorbellNotification}
              count={dismissedPreset?.alerts_count}
            >
              <Subtitle>Dismissed</Subtitle>
            </LinkWithIcon>
          </li>
        </Disclosure.Panel>
      </Disclosure>
    </>
  );
};
