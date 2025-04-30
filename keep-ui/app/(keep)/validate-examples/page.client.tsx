"use client";

import { getYamlWorkflowDefinitionSchema } from "@/entities/workflows/model/yaml.schema";
import {
  parseWorkflowYamlStringToJSON,
  getOrderedWorkflowYamlStringFromJSON,
} from "@/entities/workflows/lib/yaml-utils";
import { useProviders } from "@/utils/hooks/useProviders";
import { useMemo, useState } from "react";
import { EmptyStateCard, PageTitle, WorkflowYAMLEditor } from "@/shared/ui";
import { YamlWorkflowDefinition } from "@/entities/workflows/model/yaml.types";
import { Card, Title } from "@tremor/react";
import clsx from "clsx";
import { saveFile } from "./save-file-action";

export function ValidateExamplesPageClient({
  files,
}: {
  files: { name: string; content: string }[];
}) {
  const { data: { providers } = {} } = useProviders();

  const zodSchema = useMemo(() => {
    if (!providers) {
      return null;
    }
    return getYamlWorkflowDefinitionSchema(providers);
  }, [providers]);

  const workflows = useMemo(() => {
    if (!zodSchema) {
      return [];
    }
    return files
      .map((file) => {
        const json = parseWorkflowYamlStringToJSON(file.content);
        let workflowJson = { workflow: json };
        if ("workflow" in json) {
          workflowJson = json;
        }
        if ("alert" in json) {
          workflowJson = { workflow: json.alert };
        }
        return {
          filename: file.name,
          workflowJson,
          parseResult: zodSchema.safeParse(workflowJson),
        };
      })
      .filter(Boolean);
  }, [files, zodSchema]);

  const [selectedWorkflow, setSelectedWorkflow] = useState<{
    workflow: YamlWorkflowDefinition;
  } | null>(null);

  const [selectedFilename, setSelectedFilename] = useState<string | null>(null);

  const selectedWorkflowYaml = useMemo(() => {
    if (!selectedWorkflow) {
      return null;
    }
    return getOrderedWorkflowYamlStringFromJSON(selectedWorkflow);
  }, [selectedWorkflow]);

  if (!providers) {
    return <div>Loading providers...</div>;
  }

  if (!zodSchema) {
    return <div>Loading zod schema...</div>;
  }

  return (
    <div className="flex flex-col gap-4">
      <PageTitle>Validate Examples</PageTitle>
      <div className="flex gap-6 h-[calc(100vh-5rem)]">
        <div className=" w-2/3">
          {!selectedWorkflow ? (
            <EmptyStateCard
              className="h-full"
              title="Select a workflow to validate"
              description="Click on a workflow to validate it"
            />
          ) : (
            <Card className="h-full p-1">
              <div className="flex items-baseline justify-between p-2 border-b border-gray-200">
                <div className="flex items-center gap-2">
                  <Title className="mx-2">{selectedFilename}</Title>
                </div>
              </div>
              <WorkflowYAMLEditor
                value={selectedWorkflowYaml ?? ""}
                filename={selectedWorkflow?.workflow.id}
                onSave={(yamlString) => {
                  if (!selectedFilename) {
                    return;
                  }
                  saveFile(selectedFilename, yamlString);
                }}
              />
            </Card>
          )}
        </div>
        <div className="flex flex-col overflow-y-auto">
          <header>
            Invalid {workflows.filter((w) => !w.parseResult.success).length}/{" "}
            {workflows.length}
          </header>
          {workflows
            .filter((w) => !w.parseResult.success)
            .map((example, i) => {
              const w = example.workflowJson;
              const result = example.parseResult;
              return (
                <button
                  key={w.workflow.id}
                  type="button"
                  className={clsx(
                    "flex text-left gap-2 p-2 rounded-md cursor-pointer hover:bg-gray-200",
                    selectedWorkflow?.workflow.id === w.workflow.id
                      ? "bg-gray-200"
                      : ""
                  )}
                  onClick={(e) => {
                    e.preventDefault();
                    setSelectedWorkflow(w);
                    setSelectedFilename(example.filename);
                  }}
                >
                  {result.error ? "❌" : "✅"}
                  <div className="flex flex-col gap-1">
                    <b>{w.workflow.name}</b>
                    <span className="text-sm text-gray-500">
                      {example.filename}
                    </span>
                  </div>
                </button>
              );
            })}
        </div>
      </div>
    </div>
  );
}
