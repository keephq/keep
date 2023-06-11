import "sequential-workflow-designer/css/designer.css";
import "sequential-workflow-designer/css/designer-light.css";
import "sequential-workflow-designer/css/designer-dark.css";
import "./page.css";
import {
  Definition,
  StepsConfiguration,
  ValidatorConfiguration,
  Uid,
  Step,
  Sequence,
} from "sequential-workflow-designer";
import {
  SequentialWorkflowDesigner,
  wrapDefinition,
} from "sequential-workflow-designer-react";
import { useEffect, useState } from "react";
import StepEditor from "./editors";
import { load, JSON_SCHEMA } from "js-yaml";
import { Title } from "@tremor/react";
import { KeepStep } from "./types";

function IconUrlProvider(componentType: string, type: string): string | null {
  if (componentType === "task" && type) {
    return `${type}-icon.png`;
  }
  return null;
}

function stepValidator(
  step: Step,
  parentSequence: Sequence,
  definition: Definition
): boolean {
  return true;
}

function CanDeleteStep(step: Step, parentSequence: Sequence): boolean {
  return !step.properties["isLocked"];
}

function CanMoveStep(
  sourceSequence: any,
  step: any,
  targetSequence: Sequence,
  targetIndex: number
): boolean {
  return CanDeleteStep(step, sourceSequence);
}

// TODO: load dynamically
const toolboxConfiguration = {
  groups: [
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

function getActionOrStepObj(action: any): KeepStep {
  return {
    id: Uid.next(),
    name: action.name,
    componentType: "task",
    type: action.provider.type,
    properties: {
      config: action.provider.config,
      with: action.provider.with,
    },
  };
}

function parseAlert(alertToParse: string): Definition {
  const parsedAlertFile = load(alertToParse, { schema: JSON_SCHEMA }) as any;
  const steps = parsedAlertFile.alert.steps.map((step: any) => {
    return getActionOrStepObj(step);
  });
  const conditions = [] as any;
  parsedAlertFile.alert.actions.forEach((action: any) => {
    // This means this action always runs, there's no condition and no alias
    if (!action.condition && !action.if) {
      steps.push(getActionOrStepObj(action));
    }
    // If this is an alias, we need to find the existing condition and add this action to it
    else if (action.if) {
      const cleanIf = action.if.replace("{{", "").replace("}}", "").trim();
      const existingCondition = conditions.find(
        (a: any) => a.alias === cleanIf
      );
      existingCondition.branches.true.push(getActionOrStepObj(action));
    } else {
      action.condition.forEach((condition: any) => {
        conditions.push({
          id: Uid.next(),
          name: condition.name,
          type: condition.type,
          componentType: "switch",
          alias: condition.alias,
          properties: {
            value: condition.value,
            compare_to: condition.compare_to,
          },
          branches: {
            true: [getActionOrStepObj(action)],
            false: [],
          },
        });
      });
    }
  });
  const alert = {
    id: Uid.next(),
    name: "Workflow",
    componentType: "container",
    type: "alert",
    properties: {
      id: parsedAlertFile.alert.id,
      description: parsedAlertFile.alert.description,
    },
    sequence: [...steps, ...conditions],
  };
  return { sequence: [alert], properties: {} };
}

function Builder({
  loadedAlertFile,
  fileName,
}: {
  loadedAlertFile: string | null;
  fileName: string;
}) {
  const [definition, setDefinition] = useState(() =>
    wrapDefinition({ sequence: [], properties: {} } as Definition)
  );

  useEffect(() => {
    if (loadedAlertFile == null) {
      setDefinition(
        wrapDefinition({ sequence: [], properties: {} } as Definition)
      );
    } else {
      setDefinition(wrapDefinition(parseAlert(loadedAlertFile!)));
    }
  }, [loadedAlertFile]);

  const stepsConfiguration: StepsConfiguration = {
    iconUrlProvider: IconUrlProvider,
    canDeleteStep: CanDeleteStep,
    canMoveStep: CanMoveStep,
  };
  const validatorConfiguration: ValidatorConfiguration = {
    step: stepValidator,
  };
  return (
    <>
      {fileName ? <Title>Current loaded file: {fileName}</Title> : null}
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
    </>
  );
}

export default Builder;
