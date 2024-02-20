"use client";

import { Subtitle } from "@tremor/react";
import { LinkWithIcon } from "components/LinkWithIcon";
import { VscDebugDisconnect } from "react-icons/vsc";
import { MdOutlineEngineering } from "react-icons/md";
import { LuWorkflow } from "react-icons/lu";
import { Session } from "next-auth";

type ConfigureLinksProps = { session: Session | null };

export const ConfigureLinks = ({ session }: ConfigureLinksProps) => {
  const isNOCRole = session?.userRole === "noc";

  if (isNOCRole) {
    return null;
  }

  return (
    <div className="space-y-1">
      <Subtitle className="text-xs pl-5 text-slate-400">CONFIGURE</Subtitle>
      <ul className="space-y-2 p-2 pr-4">
        <li>
          <LinkWithIcon href="/providers" icon={VscDebugDisconnect}>
            Providers
          </LinkWithIcon>
        </li>
        <li>
          <LinkWithIcon href="/rules" icon={MdOutlineEngineering}>
            Alert Groups
          </LinkWithIcon>
        </li>
        <li>
          <LinkWithIcon href="/workflows" icon={LuWorkflow}>
            Workflows
          </LinkWithIcon>
        </li>
      </ul>
    </div>
  );
};
