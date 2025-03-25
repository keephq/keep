"use client";

import { useState } from "react";
import { WorkflowYAMLEditor } from "@/shared/ui/WorkflowYAMLEditor/ui/WorkflowYAMLEditor";
import { ResizableColumns } from "@/shared/ui/ResizableColumns/ui/ResizableColumns";
import { WorkflowBuilder } from "@/widgets/workflow-builder/workflow-builder";

const defaultYamlString = `
workflow:
  id: a9547354-2f53-48b0-a9af-81e1fcaf3a17
  name: "2"
  triggers:
    - type: manual
  description: "13"
  disabled: false
  owners: []
  services: []
  consts: {}
  steps:
    - name: console-step-1
      provider:
        type: console
        config: "{{ providers.default-console }}"
        with:
          message: hellew-1
    - name: console-step-22
      provider:
        type: console
        config: "{{ providers.default-console }}"
        with:
          message: hellew-2
    - name: console-step-3
      provider:
        type: console
        config: "{{ providers.default-console }}"
        with:
          message: hellew-322
    - name: console-step-4
      provider:
        type: console
        config: "{{ providers.default-console }}"
        with:
          message: hellew-4
  actions: []
`;

export default function WorkflowEditorPage() {
  const [yamlString, setYamlString] = useState(defaultYamlString);

  //   return (
  //     <ResizableColumns initialLeftWidth={33}>
  //       <WorkflowYAMLEditor
  //         workflowYamlString={yamlString}
  //         onChange={(value) => setYamlString(value ?? "")}
  //         filename="workflow"
  //         workflowId="a9547354-2f53-48b0-a9af-81e1fcaf3a17"
  //       />
  //       <code className="w-1/2">{yamlString}</code>
  //     </ResizableColumns>
  //   );

  return (
    <WorkflowBuilder
      workflowRaw={yamlString}
      workflowId="a9547354-2f53-48b0-a9af-81e1fcaf3a17"
      loadedYamlFileContents={""}
      providers={[]}
    />
  );
}
