"use client";

import { Button, Subtitle, Callout } from "@tremor/react";
import { LinkWithIcon } from "components/LinkWithIcon";
import { CustomPresetAlertLinks } from "components/navbar/CustomPresetAlertLinks";
import { SilencedDoorbellNotification } from "components/icons";
import { IoChevronUp } from "react-icons/io5";
import { AiOutlineGroup, AiOutlineSound, AiOutlineSwap } from "react-icons/ai";
import { FiFilter } from "react-icons/fi";
import { Disclosure } from "@headlessui/react";
import classNames from "classnames";
import { Session } from "next-auth";
import { usePresets } from "utils/hooks/usePresets";
import { useEffect, useState } from "react";
import { useTags } from "utils/hooks/useTags";
import Modal from "@/components/ui/Modal";
import CreatableMultiSelect from "@/components/ui/CreatableMultiSelect";

type AlertsLinksProps = {
  session: Session | null;
};

export const AlertsLinks = ({ session }: AlertsLinksProps) => {
  const [isTagModalOpen, setIsTagModalOpen] = useState(false);
  const [selectedTags, setSelectedTags] = useState([]);
  const { data: tags = [] } = useTags();
  const { useStaticPresets, staticPresetsOrderFromLS } = usePresets();
  const { data: fetchedPresets = [] } = useStaticPresets({
    revalidateIfStale: false,
  });

  const [staticPresets, setStaticPresets] = useState(staticPresetsOrderFromLS);

  useEffect(() => {
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

  const handleTagSelect = (newValue) => {
    setSelectedTags(newValue.map((tag) => tag.value));
  };

  return (
    <>
      <Disclosure as="div" className="space-y-1" defaultOpen>
        {({ open }) => (
          <>
            <Disclosure.Button className="w-full flex justify-between items-center p-2">
              <div className="flex items-center relative group">
                <Subtitle className="text-xs ml-2 text-gray-900 font-medium uppercase">
                  ALERTS
                </Subtitle>
                <FiFilter
                  className="absolute left-full ml-2 cursor-pointer text-gray-400 opacity-0 group-hover:opacity-100 group-hover:text-orange-500 transition-opacity"
                  size={16}
                  onClick={(e) => {
                    e.stopPropagation();
                    setIsTagModalOpen(true);
                  }}
                />
              </div>
              <IoChevronUp
                className={classNames(
                  { "rotate-180": open },
                  "mr-2 text-slate-400"
                )}
              />
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
              {session && (
                <CustomPresetAlertLinks
                  session={session}
                  selectedTags={selectedTags}
                />
              )}
              <li>
                <LinkWithIcon
                  href="/alerts/groups"
                  icon={AiOutlineGroup}
                  count={groupsPreset?.alerts_count}
                >
                  <Subtitle>Correlation</Subtitle>
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
          </>
        )}
      </Disclosure>
      {/* Tag Selection Modal */}
      <Modal
        isOpen={isTagModalOpen}
        onClose={() => setIsTagModalOpen(false)}
        className="w-[30%] max-w-screen-2xl max-h-[710px] transform overflow-auto ring-tremor bg-white p-6 text-left align-middle shadow-tremor transition-all rounded-xl"
      >
        <div className="space-y-2">
          <Subtitle>Select tags to watch</Subtitle>
          <Callout title="" color="orange">Customize your presets list by watching specific tags.</Callout>
          <CreatableMultiSelect
            value={selectedTags.map((tag) => ({
              value: tag,
              label: tag,
            }))}
            onChange={handleTagSelect}
            options={tags.map((tag) => ({
              value: tag.name,
              label: tag.name,
            }))}
            placeholder="Select or create tags"
            className="mt-4"
          />
          <Button
            size="lg"
            color="orange"
            onClick={() => setIsTagModalOpen(false)}
            tooltip="Close Modal"
          >
            Close
          </Button>
        </div>
      </Modal>
    </>
  );
};
