import React, { useEffect } from "react";
import { CiUser } from "react-icons/ci";
import { FaSitemap } from "react-icons/fa";
import { AiOutlineSwap } from "react-icons/ai";
import { Workflow } from "../models";
import { Text } from "@tremor/react";
import { DisclosureSection } from "@/components/ui/discolsure-section";
import { useRouter, useSearchParams } from "next/navigation";
import router from "next/router";

export default function SideNavBar({
  workflow,
  handleLink,
  navLink,
}: {
  navLink: string;
  workflow: Partial<Workflow>;
  handleLink: React.Dispatch<React.SetStateAction<string>>;
}) {
  const searchParams = useSearchParams();
  const router = useRouter();

  const analyseLinks = [
    {
      href: "#overview",
      icon: AiOutlineSwap,
      label: "Overview",
      key: "overview",
      isLink: false,
      handleClick: () => {
        handleLink("overview");
      },
    },
  ];

  const manageLinks = [
    {
      href: `#builder`,
      icon: FaSitemap,
      label: "Workflow Builder",
      key: "builder",
      isLink: false,
      handleClick: () => {
        handleLink("builder");
      },
    },
    {
      href: `#view_yaml`,
      icon: CiUser,
      label: "Workflow YAML definition",
      key: "view_yaml",
      isLink: false,
      handleClick: () => {
        handleLink("view_yaml");
      },
    },
  ];

  const learnLinks = [
    {
      href: `https://www.youtube.com/@keepalerting`,
      icon: FaSitemap,
      label: "Tutorials",
      isLink: true,
      newTab: true,
      key: "tutorials",
    },
    {
      href: `https://docs.keephq.dev`,
      icon: CiUser,
      label: "Documentation",
      isLink: true,
      newTab: true,
      key: "documentation",
    },
  ];

  return (
    <div className="flex flex-col gap-10 pt-6 top-20 p-1">
      <div className="h-36">
        <h1 className="text-2xl line-clamp-2 font-extrabold">
          {workflow.name}
        </h1>
        {workflow.description && (
          <Text className="line-clamp-5">
            <span>{workflow.description}</span>
          </Text>
        )}
      </div>
      <div className="space-y-8">
        <DisclosureSection
          title="Analyse"
          links={analyseLinks}
          activeLink={navLink}
        />
        <DisclosureSection
          title="Manage"
          links={manageLinks}
          activeLink={navLink}
        />
        <DisclosureSection
          title="Learn"
          links={learnLinks}
          activeLink={navLink}
        />
      </div>
    </div>
  );
}
