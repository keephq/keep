"use client";
import { useState } from "react";
import { Button, Subtitle, Callout } from "@tremor/react";
import { LinkWithIcon } from "components/LinkWithIcon";
import { CustomPresetAlertLinks } from "components/navbar/CustomPresetAlertLinks";
import { AiOutlineSwap } from "react-icons/ai";
import { FiFilter } from "react-icons/fi";
import { Disclosure } from "@headlessui/react";
import { IoChevronUp } from "react-icons/io5";
import { Session } from "next-auth";
import Modal from "@/components/ui/Modal";
import CreatableMultiSelect from "@/components/ui/CreatableMultiSelect";
import { useLocalStorage } from "utils/hooks/useLocalStorage";
import { ActionMeta, MultiValue } from "react-select";
import { useTags } from "utils/hooks/useTags";
import { usePresets } from "utils/hooks/usePresets";
import { useMounted } from "@/shared/lib/hooks/useMounted";
import clsx from "clsx";

type AlertsLinksProps = {
  session: Session | null;
};

export const AlertsLinks = ({ session }: AlertsLinksProps) => {
  const [isTagModalOpen, setIsTagModalOpen] = useState(false);
  const isMounted = useMounted();

  const [storedTags, setStoredTags] = useLocalStorage<string[]>(
    "selectedTags",
    []
  );
  const [tempSelectedTags, setTempSelectedTags] =
    useState<string[]>(storedTags);

  const { data: tags = [] } = useTags();

  // Get all presets including feed preset and localStorage state
  const { useStaticPresets, staticPresetsOrderFromLS } = usePresets();
  const { data: staticPresets = [], error: staticPresetsError } =
    useStaticPresets({
      revalidateIfStale: true,
      revalidateOnFocus: true,
    });

  const handleTagSelect = (
    newValue: MultiValue<{ value: string; label: string }>,
    actionMeta: ActionMeta<{ value: string; label: string }>
  ) => {
    setTempSelectedTags(newValue.map((tag) => tag.value));
  };

  const handleApplyTags = () => {
    setStoredTags(tempSelectedTags);
    setIsTagModalOpen(false);
  };

  const handleOpenModal = () => {
    setTempSelectedTags(storedTags);
    setIsTagModalOpen(true);
  };

  // Determine if we should show the feed link
  const shouldShowFeed = (() => {
    // If we have server data, check if feed preset exists
    if (staticPresets.length > 0) {
      return staticPresets.some((preset) => preset.name === "feed");
    }

    // If there's a server error but we have a cached feed preset, show it
    // This handles temporary API issues while maintaining functionality
    if (staticPresetsError) {
      return staticPresetsOrderFromLS?.some((preset) => preset.name === "feed");
    }

    // For the initial render on the server, always show feed
    if (!isMounted) {
      return true;
    }

    return staticPresetsOrderFromLS?.some((preset) => preset.name === "feed");
  })();

  // Get the current alerts count only if we should show feed
  const currentAlertsCount = (() => {
    if (!shouldShowFeed) {
      return 0;
    }

    // First try to get from server data
    const serverPreset = staticPresets?.find(
      (preset) => preset.name === "feed"
    );
    if (serverPreset) {
      return serverPreset.alerts_count;
    }

    // If no server data, get from localStorage
    const cachedPreset = staticPresetsOrderFromLS?.find(
      (preset) => preset.name === "feed"
    );
    return cachedPreset?.alerts_count ?? undefined;
  })();

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
                  className={clsx(
                    "absolute left-full ml-2 cursor-pointer text-gray-400 transition-opacity",
                    {
                      "opacity-100 text-orange-500": storedTags.length > 0,
                      "opacity-0 group-hover:opacity-100 group-hover:text-orange-500":
                        storedTags.length === 0,
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
                className={clsx("mr-2 text-slate-400", {
                  "rotate-180": open,
                })}
              />
            </Disclosure.Button>

            <Disclosure.Panel
              as="ul"
              className="space-y-2 overflow-auto min-w-[max-content] p-2 pr-4"
            >
              {shouldShowFeed && (
                <li>
                  <LinkWithIcon
                    href="/alerts/feed"
                    icon={AiOutlineSwap}
                    count={currentAlertsCount}
                    testId="menu-alerts-feed"
                  >
                    <Subtitle>Feed</Subtitle>
                  </LinkWithIcon>
                </li>
              )}
              {session && isMounted && (
                <CustomPresetAlertLinks
                  session={session}
                  selectedTags={storedTags}
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
