import "sequential-workflow-designer/css/designer.css";
import "sequential-workflow-designer/css/designer-light.css";
import "sequential-workflow-designer/css/designer-dark.css";
import "./page.css";
import {
  Definition,
  ToolboxConfiguration,
  StepsConfiguration,
  ValidatorConfiguration,
  Uid,
} from "sequential-workflow-designer";
import {
  SequentialWorkflowDesigner,
  wrapDefinition,
} from "sequential-workflow-designer-react";
import { useState } from "react";
import StepEditor from "./editors";

function IconUrlProvider(componentType: string, type: string): string | null {
  if (componentType === "task") {
    return `${type}-icon.png`;
  }
  return null;
}

function stepValidator(step: any, parentSequence: any, definition: any) {
  if (step.type === "query" || step.type === "notify") {
    return step.providerType ? true : false;
  }
  return true;
}

function CanDeleteStep(step: any, parentSequence: any) {
  return !step.properties["isLocked"];
}

function CanMoveStep(
  sourceSequence: any,
  step: any,
  targetSequence: any,
  targetIndex: any
) {
  return CanDeleteStep(step, sourceSequence);
}

const alert = [
  {
    id: Uid.next(),
    name: "alert",
    componentType: "container",
    type: "alert",
    properties: {
      id: "alert-id",
      description: "alert description",
      owners: [],
      services: [],
      isLocked: true,
    },
    sequence: [
      {
        id: Uid.next(),
        name: "db-no-space",
        type: "mock",
        componentType: "task",
        properties: {
          command: "df -h | grep /dev/disk3s1s1 | awk '{ print $5}'",
          command_output: "80%",
        },
        providerId: "db-server-mock",
      },
      {
        id: Uid.next(),
        type: "condition",
        componentType: "switch",
        name: "Threshold",
        properties: {
          value: "{{ steps.db-no-space.results }}",
          compare_to: "90%",
        },
        branches: {
          true: [
            {
              id: Uid.next(),
              name: "trigger-slack",
              type: "slack",
              componentType: "task",
              properties: {
                message:
                  "The disk space of {{ providers.db-server-mock.description }} is about to finish\nDisk space left: {{ steps.db-no-space.results }}",
              },
              providerId: "slack-demo",
            },
          ],
          false: [],
        },
      },
    ],
  },
];

function Builder() {
  const startDefinition: Definition = {
    sequence: alert,
    properties: {},
  };
  const [definition, setDefinition] = useState(() =>
    wrapDefinition(startDefinition)
  );

  const stepsConfiguration: StepsConfiguration = {
    iconUrlProvider: IconUrlProvider,
    canDeleteStep: CanDeleteStep,
    canMoveStep: CanMoveStep,
  };
  const validatorConfiguration: ValidatorConfiguration = {
    step: stepValidator,
  };
  const toolboxConfiguration = {
    groups: [
      // {
      //   name: "Steps",
      //   steps: [
      //     {
      //       type: "query",
      //       componentType: "task",
      //       name: "Query",
      //       properties: {},
      //     },
      //   ],
      // },
      // {
      //   name: "Actions",
      //   steps: [
      //     {
      //       type: "notify",
      //       componentType: "task",
      //       name: "Notify",
      //       properties: {},
      //     },
      //   ],
      // },
      {
        name: "Misc",
        steps: [
          {
            type: "for",
            componentType: "container",
            name: "Foreach",
            properties: {},
            sequence: [],
          },
        ],
      },
      {
        name: "Conditions",
        steps: [
          {
            type: "condition",
            componentType: "switch",
            name: "Threshold",
            properties: {
              value: "",
              compare_to: "",
            },
            branches: {
              true: [],
              false: [],
            },
          },
        ],
      },
    ],
  };
  return (
    <SequentialWorkflowDesigner
      definition={definition}
      onDefinitionChange={setDefinition}
      stepsConfiguration={stepsConfiguration}
      validatorConfiguration={validatorConfiguration}
      toolboxConfiguration={toolboxConfiguration}
      undoStackSize={10}
      controlBar={true}
      globalEditor={<></>}
      stepEditor={<StepEditor />}
    />
  );
}

export default Builder;
