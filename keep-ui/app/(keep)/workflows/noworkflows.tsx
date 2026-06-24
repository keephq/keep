import React from "react";
import { Button, Icon } from "@tremor/react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { MdArrowForwardIos } from "react-icons/md";
import { useConfig } from "utils/hooks/useConfig";
import { DynamicImageProviderIcon } from "@/components/ui";
import { EmptyStateCard } from "@/shared/ui";
import { FaSlack } from "react-icons/fa";
import {
  AcademicCapIcon,
  BellAlertIcon,
  PlusIcon,
} from "@heroicons/react/20/solid";
const WorkflowsEmptyState = () => {
  const t = useTranslations("workflows");
  const router = useRouter();
  const { data: configData } = useConfig();
  const docsUrl = configData?.KEEP_DOCS_URL || "https://docs.keephq.dev";

  const links = [
    {
      href: `${docsUrl}/platform/workflows`,
      label: t("learnMoreAboutWorkflows"),
      icon: AcademicCapIcon,
    },
    {
      href: `${docsUrl}/workflows/overview`,
      label: t("howToCreateBasicNotification"),
      icon: BellAlertIcon,
    },
    {
      href: "https://slack.keephq.dev",
      label: t("getSupportOnWorkflow"),
      icon: FaSlack,
    },
  ];

  return (
    <div className="mt-4">
      <section className="flex flex-col items-center justify-center mb-10">
        <EmptyStateCard
          noCard
          title={t("noWorkflowsAddedYet")}
          description={t("startFromScratchOrBrowse")}
          icon={() => (
            <DynamicImageProviderIcon
              src="/icons/workflow-icon.png"
              alt="loading"
              width={200}
              height={200}
            />
          )}
        >
          <Button
            icon={PlusIcon}
            className="mt-4 px-6 py-2"
            color="orange"
            variant="primary"
            onClick={() => {
              router.push("/workflows/builder");
            }}
          >
            {t("createNewWorkflow")}
          </Button>
          <div className="mt-10 divide-y flex flex-col border border-gray-200 rounded bg-white shadow text-sm">
            {links.map((link) => (
              <a
                key={link.href}
                href={link.href}
                target="_blank"
                className="flex items-center p-2 bg-white hover:bg-gray-100 transition cursor-pointer gap-4"
              >
                <div className="flex flex-row items-center gap-2">
                  <Icon icon={link.icon} className="w-4 h-4 text-gray-500" />
                  <p className="truncate">{link.label}</p>
                </div>
                <span className="ml-auto flex items-center">
                  <MdArrowForwardIos className="w-4 h-4 text-gray-500 ml-2" />
                </span>
              </a>
            ))}
          </div>
        </EmptyStateCard>
      </section>
    </div>
  );
};

export default WorkflowsEmptyState;
