import React, { useState } from "react";
import { CiUser } from "react-icons/ci";
import { FaSitemap } from "react-icons/fa";
import { AiOutlineSwap } from "react-icons/ai";
import { Workflow } from "../models";
import { Text } from "@tremor/react";
import { DisclosureSection } from "@/components/ui/discolsure-section";
import { useWorkflowRun } from "utils/hooks/useWorkflowRun";
import Modal from "react-modal";
import BuilderWorkflowTestRunModalContent from "../builder/builder-workflow-testrun-modal";
import BuilderModalContent from "../builder/builder-modal";

export default function SideNavBar({ workflow }: { workflow: Workflow }) {
  const [viewYaml, setviewYaml] = useState(false);

  const analyseLinks = [
    {
      href: `/workflows/${workflow.id}`,
      icon: AiOutlineSwap,
      label: "Overview",
      isLink: true,
    },
  ];

  const manageLinks = [
    {
      href: `/workflows/builder/${workflow.id}`,
      icon: FaSitemap,
      label: "Workflow Builder",
      isLink: true,
    },
    {
      href: `/workflows/builder/${workflow.id}`,
      icon: CiUser,
      label: "Workflow YAML definition",
      isLink: false,
      handleClick: () => {
        setviewYaml(true);
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
    },
    {
      href: `https://docs.keephq.dev`,
      icon: CiUser,
      label: "Documentation",
      isLink: true,
      newTab: true,
    },
  ];

  return (
    <div className="flex flex-col gap-10 pt-6 top-20 p-1 max-w-[270px]">
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
        <DisclosureSection title="Analyse" links={analyseLinks} />
        <DisclosureSection title="Manage" links={manageLinks} />
        <DisclosureSection title="Learn" links={learnLinks} />
      </div>
      <Modal
        isOpen={viewYaml}
        onRequestClose={() => {
          setviewYaml(false);
        }}
        className="bg-gray-50 p-4 md:p-10 mx-auto max-w-7xl mt-20 border border-orange-600/50 rounded-md"
      >
        <BuilderModalContent
          closeModal={() => {
            setviewYaml(false);
          }}
          compiledAlert={workflow.workflow_raw!}
          id={workflow.id}
        />
      </Modal>
    </div>
  );
}
