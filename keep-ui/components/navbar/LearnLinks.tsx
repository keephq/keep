"use client";

import { Subtitle } from "@tremor/react";
import { LinkWithIcon } from "components/LinkWithIcon";
import { AiOutlineBook } from "react-icons/ai";

export const LearnLinks = () => {
  return (
    <div className="space-y-1">
      <Subtitle className="text-xs pl-5 text-slate-400">LEARN</Subtitle>
      <ul className="space-y-2 p-2 pr-4">
        <li>
          <LinkWithIcon
            href="https://docs.keephq.dev"
            icon={AiOutlineBook}
            target="_blank"
          >
            Documentation
          </LinkWithIcon>
        </li>
      </ul>
    </div>
  );
};
