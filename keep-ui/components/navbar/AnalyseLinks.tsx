"use client";

import { Subtitle } from "@tremor/react";
import { usePresets } from "utils/hooks/usePresets";
import { LinkWithIcon } from "components/LinkWithIcon";
import { AiOutlineSwap, AiOutlineAlert, AiOutlineDelete } from "react-icons/ai";

export const AnalyseLinks = () => {
  const { useAllPresets } = usePresets();
  const { data: presets = [] } = useAllPresets();

  return (
    <div className="space-y-2">
      <Subtitle className="text-xs pl-3">ANALYSE</Subtitle>
      <ul className="space-y-2 max-h-60 overflow-auto">
        <li>
          <LinkWithIcon href="/alerts/feed" icon={AiOutlineAlert}>
            Feed
          </LinkWithIcon>
        </li>
        <li>
          <LinkWithIcon href="/alerts/deleted" icon={AiOutlineDelete}>
            Deleted
          </LinkWithIcon>
        </li>
        {presets.map((preset) => (
          <li key={preset.id}>
            <LinkWithIcon href={`/alerts/${preset.name}`} icon={AiOutlineSwap}>
              Providers
            </LinkWithIcon>
          </li>
        ))}
      </ul>
    </div>
  );
};
