"use client";

import {
  Card,
  Tab,
  TabGroup,
  TabList,
  TabPanel,
  TabPanels,
} from "@tremor/react";
import React, { useState, useEffect } from "react";
import {
  ArrowUpRightIcon,
  CodeBracketIcon,
  WrenchIcon,
} from "@heroicons/react/24/outline";
import { Workflow } from "@/shared/api/workflows";
import useSWR from "swr";
import { WorkflowBuilderPageClient } from "../builder/page.client";
import WorkflowOverview from "./workflow-overview";
import { useApi } from "@/shared/lib/hooks/useApi";
import { useConfig } from "utils/hooks/useConfig";
import { AiOutlineSwap } from "react-icons/ai";
import { ErrorComponent, TabNavigationLink, YAMLCodeblock } from "@/shared/ui";
import MonacoYAMLEditor from "@/shared/ui/YAMLCodeblock/ui/MonacoYAMLEditor";
import Skeleton from "react-loading-skeleton";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

export default function WorkflowDetailPage({
  params,
  initialData,
}: {
  params: { workflow_id: string };
  initialData?: Workflow;
}) {
  const api = useApi();
  const { data: configData } = useConfig();
  const [tabIndex, setTabIndex] = useState(0);
  const searchParams = useSearchParams();
  const router = useRouter();

  // Set initial tab based on URL query param
  useEffect(() => {
    const tab = searchParams.get("tab");
    if (tab === "yaml") {
      setTabIndex(2);
    } else if (tab === "builder") {
      setTabIndex(1);
    } else {
      setTabIndex(0);
    }
  }, [searchParams]);

  const {
    data: workflow,
    isLoading,
    error,
  } = useSWR<Workflow>(
    api.isReady() ? `/workflows/${params.workflow_id}` : null,
    (url: string) => api.get(url),
    {
      fallbackData: initialData,
    }
  );

  const docsUrl = configData?.KEEP_DOCS_URL || "https://docs.keephq.dev";

  if (error) {
    return <ErrorComponent error={error} />;
  }

  const handleTabChange = (index: number) => {
    setTabIndex(index);
    const basePath = `/workflows/${params.workflow_id}`;
    switch (index) {
      case 0:
        router.push(basePath);
        break;
      case 1:
        router.push(`${basePath}?tab=builder`);
        break;
      case 2:
        router.push(`${basePath}?tab=yaml`);
        break;
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <TabGroup index={tabIndex} onIndexChange={handleTabChange}>
        <TabList>
          <Tab icon={AiOutlineSwap}>Overview</Tab>
          <Tab icon={WrenchIcon}>Builder</Tab>
          <Tab icon={CodeBracketIcon}>YAML Definition</Tab>
          <TabNavigationLink
            href="https://www.youtube.com/@keepalerting"
            icon={ArrowUpRightIcon}
            target="_blank"
          >
            Tutorials
          </TabNavigationLink>
          <TabNavigationLink
            href={`${docsUrl}/workflows`}
            icon={ArrowUpRightIcon}
            target="_blank"
          >
            Documentation
          </TabNavigationLink>
        </TabList>
        <TabPanels>
          <TabPanel>
            <WorkflowOverview workflow_id={params.workflow_id} />
          </TabPanel>
          <TabPanel>
            {!workflow ? (
              <Skeleton className="w-full h-full" />
            ) : (
              <Card className="h-[calc(100vh-150px)]">
                <WorkflowBuilderPageClient
                  workflowRaw={workflow.workflow_raw}
                  workflowId={workflow.id}
                />
              </Card>
            )}
          </TabPanel>
          <TabPanel>
            {!workflow ? (
              <Skeleton className="w-full h-full" />
            ) : (
              <Card className="h-[calc(100vh-200px)]">
                <MonacoYAMLEditor
                  yamlString={workflow.workflow_raw!}
                  filename={workflow.id ?? "workflow"}
                  workflowId={workflow.id}
                />
              </Card>
            )}
          </TabPanel>
        </TabPanels>
      </TabGroup>
    </div>
  );
}
