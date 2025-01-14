"use client";

import {
  Card,
  Tab,
  TabGroup,
  TabList,
  TabPanel,
  TabPanels,
} from "@tremor/react";
import React, { useState } from "react";
import {
  ArrowUpRightIcon,
  CodeBracketIcon,
  WrenchIcon,
} from "@heroicons/react/24/outline";
import Loading from "@/app/(keep)/loading";
import { Workflow } from "@/shared/api/workflows";
import useSWR from "swr";
import { WorkflowBuilderPageClient } from "../builder/page.client";
import WorkflowOverview from "./workflow-overview";
import { useApi } from "@/shared/lib/hooks/useApi";
import { useConfig } from "utils/hooks/useConfig";
import { AiOutlineSwap } from "react-icons/ai";
import { ErrorComponent, TabNavigationLink, YAMLCodeblock } from "@/shared/ui";

export default function WorkflowDetailPage({
  params,
}: {
  params: { workflow_id: string };
}) {
  const api = useApi();
  const { data: configData } = useConfig();
  const [tabIndex, setTabIndex] = useState(0);

  const {
    data: workflow,
    isLoading,
    error,
  } = useSWR<Partial<Workflow>>(
    api.isReady() ? `/workflows/${params.workflow_id}` : null,
    (url: string) => api.get(url)
  );

  const docsUrl = configData?.KEEP_DOCS_URL || "https://docs.keephq.dev";

  if (error) {
    return <ErrorComponent error={error} />;
  }

  if (isLoading || !workflow) {
    return <Loading />;
  }

  // TODO: change url to /workflows/[workflow_id]/[tab] or use the file-based routing
  const handleTabChange = (index: number) => {
    setTabIndex(index);
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
            <Card className="h-[calc(100vh-150px)]">
              <WorkflowBuilderPageClient
                workflowRaw={workflow.workflow_raw}
                workflowId={workflow.id}
              />
            </Card>
          </TabPanel>
          <TabPanel>
            <Card>
              <YAMLCodeblock
                yamlString={workflow.workflow_raw!}
                filename={workflow.id ?? "workflow"}
              />
            </Card>
          </TabPanel>
        </TabPanels>
      </TabGroup>
    </div>
  );
}
