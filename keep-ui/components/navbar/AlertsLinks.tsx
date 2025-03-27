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
import { usePresets } from "@/entities/presets/model/usePresets";
import { useMounted } from "@/shared/lib/hooks/useMounted";
import clsx from "clsx";
import { useAlerts } from "@/utils/hooks/useAlerts";

type AlertsLinksProps = {
  session: Session | null;
};

export const AlertsLinks = ({ session }: AlertsLinksProps) => {
  const [isTagModalOpen, setIsTagModalOpen] = useState(false);
  const isMounted = useMounted();
  const { useLastAlerts } = useAlerts();

  const [storedTags, setStoredTags] = useLocalStorage<string[]>(
    "selectedTags",
    []
  );
  const [tempSelectedTags, setTempSelectedTags] =
    useState<string[]>(storedTags);

  const { data: tags = [] } = useTags();

  const { staticPresets, error: staticPresetsError } = usePresets({
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
    // For the initial render on the server, always show feed
    if (!isMounted || (!staticPresets && !staticPresetsError)) {
      return true;
    }

    return staticPresets?.some((preset) => preset.name === "feed");
  })();

  const { isLoading: isAsyncLoading, totalCount: feedAlertsTotalCount } =
    useLastAlerts({
      cel: shouldShowFeed ? undefined : "",
      limit: 0,
      offset: 0,
    });

  return (
    <>
      <Disclosure as="div" className="space-y-1" defaultOpen>
        {({ open }) => (
          <>
            <Disclosure.Button className="w-full flex justify-between items-center px-2">
              <div className="flex items-center relative group">
                <Subtitle className="text-xs ml-2 text-gray-900 font-medium uppercase">
                  Alerts
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

            <Disclosure.Panel as="ul" className="space-y-2 overflow-auto px-2">
              {shouldShowFeed && (
                <li>
                  <LinkWithIcon
                    href="/alerts/feed"
                    icon={AiOutlineSwap}
                    count={feedAlertsTotalCount}
                    testId="menu-alerts-feed"
                  >
                    <Subtitle>Feed</Subtitle>
                  </LinkWithIcon>
                </li>
              )}
              <CustomPresetAlertLinks selectedTags={storedTags} />
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
