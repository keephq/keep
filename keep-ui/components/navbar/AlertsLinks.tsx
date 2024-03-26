"use client";

import { Subtitle } from "@tremor/react";
import { usePresets } from "utils/hooks/usePresets";
import { LinkWithIcon } from "components/LinkWithIcon";
import { LinkWithIconAndAction } from "components/LinkWithIconAndAction";
import { AiOutlineSwap, AiOutlineDelete } from "react-icons/ai";
import {
  IoNotificationsOffOutline,
  IoNotificationsOutline,
  IoChevronUp,
} from "react-icons/io5";
import { Disclosure } from "@headlessui/react";
import classNames from "classnames";
import { Session } from "next-auth";
import { getApiURL } from "utils/apiUrl";
import { toast } from "react-toastify";

type AlertsLinksProps = {
  session: Session | null;
};

export const AlertsLinks = ({ session }: AlertsLinksProps) => {
  const apiUrl = getApiURL();
  const { useAllPresets } = usePresets();
  const { data: presets = [], mutate: presetsMutator } = useAllPresets({
    revalidateIfStale: false,
  });

  const deletePreset = async (presetId: string, presetName: string) => {
    const isDeleteConfirmed = confirm(
      `You are about to delete preset ${presetName}. Are you sure?`
    );

    if (isDeleteConfirmed) {
      const response = await fetch(`${apiUrl}/preset/${presetId}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${session?.accessToken}`,
        },
      });
      if (response.ok) {
        toast(`Preset ${presetName} deleted!`, {
          position: "top-left",
          type: "success",
        });
        presetsMutator();
      }
    }
  };

  return (
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
        className="space-y-2 max-h-[40vh] overflow-auto min-w-[max-content] p-2 pr-4"
      >
        <li>
          <LinkWithIcon href="/alerts/feed" icon={IoNotificationsOutline}>
            Feed [All]
          </LinkWithIcon>
        </li>
        {presets.map((preset) => (
          <li key={preset.id}>
            <LinkWithIconAndAction
              href={`/alerts/${preset.name.toLowerCase()}`}
              icon={AiOutlineSwap}
              actionIcon={AiOutlineDelete}
              actionOnClick={() => deletePreset(preset.id, preset.name)}
            >
              {preset.name}
            </LinkWithIconAndAction>
          </li>
        ))}
        <li>
          <LinkWithIcon href="/alerts/groups" icon={IoNotificationsOffOutline}>
            Groups
          </LinkWithIcon>
        </li>
        <li>
          <LinkWithIcon
            href="/alerts/dismissed"
            icon={IoNotificationsOffOutline}
          >
            Dismissed
          </LinkWithIcon>
        </li>
        <li>
          <LinkWithIcon href="/alerts/deleted" icon={AiOutlineDelete}>
            Deleted
          </LinkWithIcon>
        </li>
      </Disclosure.Panel>
    </Disclosure>
  );
};
