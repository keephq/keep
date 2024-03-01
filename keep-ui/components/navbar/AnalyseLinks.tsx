"use client";

import { Subtitle } from "@tremor/react";
import { usePresets } from "utils/hooks/usePresets";
import { LinkWithIcon } from "components/LinkWithIcon";
import {
  AiOutlineSwap,
  AiOutlineAlert,
  AiOutlineDelete,
  AiOutlineGroup,
} from "react-icons/ai";
import { IoNotificationsOffOutline } from "react-icons/io5";

export const AnalyseLinks = () => {
  const { useAllPresets } = usePresets();
  const { data: presets = [] } = useAllPresets({ revalidateIfStale: false });

  return (
    <div className="space-y-1">
      <Subtitle className="text-xs pl-5 text-slate-400">ANALYSE</Subtitle>
      <ul className="space-y-2 max-h-56 overflow-auto min-w-[max-content] p-2 pr-4">
        <li>
          <LinkWithIcon href="/alerts/feed" icon={AiOutlineAlert}>
            Feed
          </LinkWithIcon>
        </li>
        <li>
          <LinkWithIcon href="/alerts/dismissed" icon={IoNotificationsOffOutline}>
            Dismissed
          </LinkWithIcon>
        </li>
        <li>
          <LinkWithIcon href="/alerts/deleted" icon={AiOutlineDelete}>
            Deleted
          </LinkWithIcon>
        </li>
        <li>
          <LinkWithIcon href="/alerts/groups" icon={AiOutlineGroup}>
            Groups
          </LinkWithIcon>
        </li>
        {presets.map((preset) => (
          <li key={preset.id}>
            <LinkWithIcon
              href={`/alerts/${preset.name.toLowerCase()}`}
              icon={AiOutlineSwap}
            >
              {preset.name}
            </LinkWithIcon>
          </li>
        ))}
      </ul>
    </div>
  );
};
