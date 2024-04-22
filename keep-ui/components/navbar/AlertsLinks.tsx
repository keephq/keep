"use client";

import { Badge, Subtitle } from "@tremor/react";

import { LinkWithIcon } from "components/LinkWithIcon";
import { CustomPresetAlertLinks } from "components/navbar/CustomPresetAlertLinks";
import {
  DoorbellNotification,
  SilencedDoorbellNotification,
  Trashcan,
} from "components/icons";
import { IoChevronUp } from "react-icons/io5";
import { AiOutlineGroup, AiOutlineSound, AiOutlineSwap } from "react-icons/ai";
import { Disclosure } from "@headlessui/react";
import classNames from "classnames";
import { Session } from "next-auth";
import { usePresets } from "utils/hooks/usePresets";
import { useEffect, useState } from "react";
import ReactPlayer from 'react-player';

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
  const [playAlertSound, setPlayAlertSound] = useState(false);

  useEffect(() => {
    // Convert both arrays to string to perform a comparison
    if (fetchedPresets.length > 0 && JSON.stringify(staticPresets) !== JSON.stringify(staticPresetsOrderFromLS)) {
      setStaticPresets(staticPresetsOrderFromLS);
    }
  }, [fetchedPresets]);



  const mainPreset = staticPresets.find((preset) => preset.name === "feed");
  const deletedPreset = staticPresets.find((preset) => preset.name === "deleted");
  const dismissedPreset = staticPresets.find((preset) => preset.name === "dismissed");
  const groupsPreset = staticPresets.find((preset) => preset.name === "groups");

  // if feed or groups are should do noise now, play alert sound
  useEffect(() => {
    // filter out dismissed and deleted
    const noisyPresets = staticPresets.filter(
      (preset) => !["deleted", "dismissed"].includes(preset.name)
    );
    const anyNoisyNow = noisyPresets.some((preset) => preset.should_do_noise_now);
    setPlayAlertSound(anyNoisyNow);
  }, [staticPresets]);

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
                  "mr-2 text-slate-400"
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
              iconOverride={
                mainPreset?.should_do_noise_now ? AiOutlineSound :
                mainPreset?.is_noisy ? AiOutlineSound : undefined
              }
              count={mainPreset?.alerts_count}
              shouldPulse={mainPreset?.should_do_noise_now}
            >
              Feed
            </LinkWithIcon>
          </li>
          {session && <CustomPresetAlertLinks session={session} setPlayAlertSound={setPlayAlertSound}/>}
          <li>
            <LinkWithIcon href="/alerts/groups" icon={AiOutlineGroup} count={groupsPreset?.alerts_count}>
              Correlation
            </LinkWithIcon>
          </li>
          <li>
            <LinkWithIcon
              href="/alerts/dismissed"
              icon={SilencedDoorbellNotification}
              count={dismissedPreset?.alerts_count}
            >
              Dismissed
            </LinkWithIcon>
          </li>
          <li>
            <LinkWithIcon href="/alerts/deleted" icon={Trashcan} count={deletedPreset?.alerts_count}>
              Deleted
            </LinkWithIcon>
          </li>
        </Disclosure.Panel>
      </Disclosure>
      {/* React Player for playing alert sound */}
      <ReactPlayer
        url="/music/alert.mp3"
        playing={playAlertSound}
        volume={0.5}
        loop={true}
        width="0"
        height="0"
        playsinline
      />
   </>

  );
};
