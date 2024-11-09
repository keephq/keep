"use client";

import { Button, Subtitle, Callout } from "@tremor/react";
import { LinkWithIcon } from "components/LinkWithIcon";
import { CustomPresetAlertLinks } from "components/navbar/CustomPresetAlertLinks";
import { AiOutlineSwap } from "react-icons/ai";
import { FiFilter } from "react-icons/fi";
import { Disclosure } from "@headlessui/react";
import classNames from "classnames";
import { Session } from "next-auth";
import { useState, useEffect } from "react";
import { useTags } from "utils/hooks/useTags";
import Modal from "@/components/ui/Modal";
import CreatableMultiSelect from "@/components/ui/CreatableMultiSelect";
import { useLocalStorage } from "utils/hooks/useLocalStorage";
import { ActionMeta, MultiValue } from "react-select";
import { IoChevronUp } from "react-icons/io5";

type AlertsLinksProps = {
  session: Session | null;
};

type FeedPreset = {
  id: string;
  name: string;
  alerts_count: number;
};

const DEFAULT_FEED_PRESET: FeedPreset = {
  id: "feed",
  name: "feed",
  alerts_count: 0,
};

export const AlertsLinks = ({ session }: AlertsLinksProps) => {
  const [isTagModalOpen, setIsTagModalOpen] = useState(false);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [tempSelectedTags, setTempSelectedTags] = useState<string[]>([]);
  const { data: tags = [] } = useTags();
  const [storedTags, setStoredTags] = useLocalStorage<string[]>(
    "selectedTags",
    []
  );
  const [feedPreset, setFeedPreset] = useLocalStorage<FeedPreset>(
    "feedPreset",
    DEFAULT_FEED_PRESET
  );

  useEffect(() => {
    if (JSON.stringify(selectedTags) !== JSON.stringify(storedTags)) {
      setSelectedTags(storedTags);
    }
  }, []);

  const handleTagSelect = (
    newValue: MultiValue<{ value: string; label: string }>,
    actionMeta: ActionMeta<{ value: string; label: string }>
  ) => {
    setTempSelectedTags(newValue.map((tag) => tag.value));
  };

  const handleApplyTags = () => {
    setSelectedTags(tempSelectedTags);
    setStoredTags(tempSelectedTags);
    setIsTagModalOpen(false);
  };

  const handleOpenModal = () => {
    setTempSelectedTags(selectedTags);
    setIsTagModalOpen(true);
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
                  className={classNames(
                    "absolute left-full ml-2 cursor-pointer text-gray-400 transition-opacity",
                    {
                      "opacity-100 text-orange-500": selectedTags.length > 0,
                      "opacity-0 group-hover:opacity-100 group-hover:text-orange-500":
                        selectedTags.length === 0,
                    }
                  )}
                  size={16}
                  onClick={(e) => {
                    e.stopPropagation();
                    handleOpenModal();
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
                  count={feedPreset.alerts_count}
                  testId="menu-alerts-feed"
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
            </Disclosure.Panel>
          </>
        )}
      </Disclosure>
      <Modal
        isOpen={isTagModalOpen}
        onClose={() => setIsTagModalOpen(false)}
        className="w-[30%] max-w-screen-2xl max-h-[710px] transform overflow-auto ring-tremor bg-white p-6 text-left align-middle shadow-tremor transition-all rounded-xl"
      >
        <div className="space-y-2">
          <Subtitle>Select tags to watch</Subtitle>
          <Callout title="" color="orange">
            Customize your presets list by watching specific tags.
          </Callout>
          <CreatableMultiSelect
            value={tempSelectedTags.map((tag) => ({
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
          <div className="flex justify-end space-x-2.5">
            <Button
              size="lg"
              variant="secondary"
              color="orange"
              onClick={() => setIsTagModalOpen(false)}
              tooltip="Close Modal"
            >
              Close
            </Button>
            <Button
              size="lg"
              color="orange"
              onClick={handleApplyTags}
              tooltip="Apply Tags"
            >
              Apply
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
};
