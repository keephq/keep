// TODO: types, cleanup, etc.
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
  StepDefinition,
} from "sequential-workflow-designer";
import {
  SequentialWorkflowDesigner,
  wrapDefinition,
} from "sequential-workflow-designer-react";
import { useEffect, useState } from "react";
import StepEditor, { GlobalEditor } from "./editors";
import { load, JSON_SCHEMA } from "js-yaml";
import { Title } from "@tremor/react";
import { KeepStep } from "./types";
import { Provider } from "../providers/providers";

function IconUrlProvider(componentType: string, type: string): string | null {
  if (componentType === "task" && type) {
    return `${type.replace("step-", "").replace("action-", "")}-icon.png`;
  }
  return null;
}

function globalValidator(definition: Definition): boolean {
  return definition.sequence.length <= 1;
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

function IsStepDraggable(step: Step, parentSequence: Sequence): boolean {
  return CanDeleteStep(step, parentSequence);
}

function CanMoveStep(
  sourceSequence: any,
  step: any,
  targetSequence: Sequence,
  targetIndex: number
): boolean {
  return CanDeleteStep(step, sourceSequence);
}

const stepsConfiguration: StepsConfiguration = {
  iconUrlProvider: IconUrlProvider,
  canDeleteStep: CanDeleteStep,
  canMoveStep: CanMoveStep,
  isDraggable: IsStepDraggable,
};

const validatorConfiguration: ValidatorConfiguration = {
  step: stepValidator,
  root: globalValidator,
};

function toolboxConfiguration(providers: { [providerType: string]: Provider }) {
  /**
   * Generate the toolbox configuration
   */
  const [steps, actions] = Object.values(providers).reduce(
    ([steps, actions], provider) => {
      const step = {
        name: provider.type,
        componentType: "task",
        type: provider.type,
        properties: { ...provider.config },
      };
      if (provider.can_notify)
        steps.push({ ...step, type: `step-${provider.type}` });
      if (provider.can_query)
        actions.push({ ...step, type: `action-${provider.type}` });
      return [steps, actions];
    },
    [[] as StepDefinition[], [] as StepDefinition[]]
  );
  return {
    groups: [
      {
        name: "Steps",
        steps: steps,
      },
      {
        name: "Actions",
        steps: actions,
      },
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
}

function getActionOrStepObj(
  actionOrStep: any,
  type: "action" | "step"
): KeepStep {
  /**
   * Generate a step or action definition (both are kinda the same)
   */
  return {
    id: Uid.next(),
    name: actionOrStep.name,
    componentType: "task",
    type: `${type}-${actionOrStep.provider.type}`,
    properties: {
      config: actionOrStep.provider.config,
      with: actionOrStep.provider.with,
    },
  };
}

function generateCondition(condition: any, action: any): any {
  const generatedCondition = {
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
      true: [getActionOrStepObj(action, "action")],
      false: [],
    },
  };

  if (action.foreach) {
    return {
      id: Uid.next(),
      type: "for",
      componentType: "container",
      name: "Foreach",
      properties: {
        value: action.foreach,
      },
      sequence: [generatedCondition],
    };
  }

  return generatedCondition;
}

function generateAlert(
  alertId: string,
  description: string,
  steps: Step[],
  conditions: Step[]
): Definition {
  /**
   * Generate the alert definition
   */
  const alert = {
    id: Uid.next(),
    name: "Workflow",
    componentType: "container",
    type: "alert",
    properties: {
      id: alertId,
      description: description,
      isLocked: true,
    },
    sequence: [...steps, ...conditions],
  };
  return { sequence: [alert], properties: {} };
}

function parseAlert(alertToParse: string): Definition {
  /**
   * Parse the alert file and generate the definition
   */
  const parsedAlertFile = load(alertToParse, { schema: JSON_SCHEMA }) as any;
  const steps = parsedAlertFile.alert.steps.map((step: any) => {
    return getActionOrStepObj(step, "step");
  });
  const conditions = [] as any;
  parsedAlertFile.alert.actions.forEach((action: any) => {
    // This means this action always runs, there's no condition and no alias
    if (!action.condition && !action.if) {
      steps.push(getActionOrStepObj(action, "action"));
    }
    // If this is an alias, we need to find the existing condition and add this action to it
    else if (action.if) {
      const cleanIf = action.if.replace("{{", "").replace("}}", "").trim();
      const existingCondition = conditions.find(
        (a: any) => a.alias === cleanIf
      );
      existingCondition?.branches.true.push(
        getActionOrStepObj(action, "action")
      );
    } else {
      action.condition.forEach((condition: any) => {
        conditions.push(generateCondition(condition, action));
      });
    }
  });

  return generateAlert(
    parsedAlertFile.alert.id,
    parsedAlertFile.alert.description,
    steps,
    conditions
  );
}

interface Props {
  loadedAlertFile: string | null;
  fileName: string;
  providers: { [providerType: string]: Provider };
}

function Builder({ loadedAlertFile, fileName, providers }: Props) {
  const [definition, setDefinition] = useState(() =>
    wrapDefinition({ sequence: [], properties: {} } as Definition)
  );

  useEffect(() => {
    if (loadedAlertFile == null) {
      setDefinition(
        wrapDefinition(
          generateAlert("new-alert-id", "new-alert-description", [], [])
        )
      );
    } else {
      setDefinition(wrapDefinition(parseAlert(loadedAlertFile!)));
    }
  }, [loadedAlertFile]);

  return (
    <>
      {fileName ? <Title>Current loaded file: {fileName}</Title> : null}
      <SequentialWorkflowDesigner
        definition={definition}
        onDefinitionChange={setDefinition}
        stepsConfiguration={stepsConfiguration}
        validatorConfiguration={validatorConfiguration}
        toolboxConfiguration={toolboxConfiguration(providers)}
        undoStackSize={10}
        controlBar={true}
        globalEditor={<GlobalEditor />}
        stepEditor={<StepEditor />}
      />
    </>
  );
}

export default Builder;
