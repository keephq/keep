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
  KeyIcon,
} from "@heroicons/react/24/outline";
import { Workflow } from "@/shared/api/workflows";
import { WorkflowBuilderWidget } from "@/widgets/workflow-builder";
import WorkflowOverview from "./workflow-overview";
import WorkflowSecrets from "./workflow-secrets";
import { useConfig } from "utils/hooks/useConfig";
import { AiOutlineSwap } from "react-icons/ai";
import { ErrorComponent, TabNavigationLink } from "@/shared/ui";
import Skeleton from "react-loading-skeleton";
import { useRouter, useSearchParams } from "next/navigation";
import { useWorkflowDetail } from "@/entities/workflows/model/useWorkflowDetail";
import { WorkflowYAMLEditorStandalone } from "@/shared/ui/WorkflowYAMLEditor/ui/WorkflowYAMLEditorStandalone";
import { getOrderedWorkflowYamlString } from "@/entities/workflows/lib/yaml-utils";
import { PiClockCounterClockwise } from "react-icons/pi";
import { WorkflowRevisions } from "./workflow-revisions";

const TABS_KEYS = ["overview", "builder", "yaml", "versions", "secrets"];

function getTabIndex(tabKey: string) {
  const index = TABS_KEYS.indexOf(tabKey);
  if (index !== -1) {
    return index;
  }
  return 0;
}

export default function WorkflowDetailPage({
  params,
  initialData,
}: {
  params: { workflow_id: string };
  initialData?: Workflow;
}) {
  const { data: configData } = useConfig();
  const searchParams = useSearchParams();
  const [tabIndex, setTabIndex] = useState(
    getTabIndex(searchParams.get("tab") ?? "")
  );
  const router = useRouter();

  // Set initial tab based on URL query param
  useEffect(() => {
    const tab = searchParams.get("tab");
    setTabIndex(getTabIndex(tab ?? ""));
  }, [searchParams]);

  const { workflow, isLoading, error } = useWorkflowDetail(
    params.workflow_id,
    null,
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
    const tabKey = TABS_KEYS[index];
    if (tabKey) {
      router.push(`${basePath}?tab=${tabKey}`);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <TabGroup index={tabIndex} onIndexChange={handleTabChange}>
        <TabList>
          <Tab icon={AiOutlineSwap}>Overview</Tab>
          <Tab icon={WrenchIcon}>Builder</Tab>
          <Tab icon={CodeBracketIcon}>YAML Definition</Tab>
          <Tab icon={PiClockCounterClockwise}>Versions</Tab>
          <Tab icon={KeyIcon}>Secrets</Tab>
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
          <TabPanel id="overview">
            <WorkflowOverview
              workflow={workflow ?? null}
              workflow_id={params.workflow_id}
            />
          </TabPanel>
          <TabPanel id="builder">
            {!workflow ? (
              <Skeleton className="w-full h-full" />
            ) : (
              <Card className="h-[calc(100vh-12rem)] p-0 overflow-hidden">
                <WorkflowBuilderWidget
                  workflowRaw={workflow.workflow_raw}
                  workflowId={workflow.id}
                />
              </Card>
            )}
          </TabPanel>
          <TabPanel id="yaml">
            {!workflow || !workflow.workflow_raw ? (
              <Skeleton className="w-full h-full" />
            ) : (
              <Card className="h-[calc(100vh-12rem)] p-0">
                <WorkflowYAMLEditorStandalone
                  workflowId={workflow.id}
                  yamlString={getOrderedWorkflowYamlString(
                    workflow.workflow_raw
                  )}
                  data-testid="wf-detail-yaml-editor"
                />
              </Card>
            )}
          </TabPanel>
          <TabPanel id="versions">
            <WorkflowRevisions
              workflowId={params.workflow_id}
              currentRevision={workflow?.revision ?? null}
            />
          </TabPanel>
          <TabPanel id="secrets">
            <WorkflowSecrets workflowId={params.workflow_id} />
          </TabPanel>
        </TabPanels>
      </TabGroup>
    </div>
  );
}
