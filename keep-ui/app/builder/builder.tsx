import "sequential-workflow-designer/css/designer.css";
import "sequential-workflow-designer/css/designer-light.css";
import "sequential-workflow-designer/css/designer-dark.css";
import "./page.css";
import {
  Definition,
  StepsConfiguration,
  ValidatorConfiguration,
  Step,
  Sequence,
  BranchedStep,
  SequentialStep,
} from "sequential-workflow-designer";
import {
  SequentialWorkflowDesigner,
  wrapDefinition,
} from "sequential-workflow-designer-react";
import { useEffect, useState } from "react";
import StepEditor, { GlobalEditor } from "./editors";
import { Callout, Title } from "@tremor/react";
import { Provider } from "../providers/providers";
import { parseAlert, generateAlert, getToolboxConfiguration } from "./utils";
import {
  CheckCircleIcon,
  ExclamationCircleIcon,
} from "@heroicons/react/20/solid";

interface Props {
  loadedAlertFile: string | null;
  fileName: string;
  providers: { [providerType: string]: Provider };
}

function Builder({ loadedAlertFile, fileName, providers }: Props) {
  const [definition, setDefinition] = useState(() =>
    wrapDefinition({ sequence: [], properties: {} } as Definition)
  );
  const [validationError, setValidationError] = useState<string | null>(null);

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

  function globalValidator(definition: Definition): boolean {
    const onlyOneAlert = definition.sequence.length === 1;
    if (!onlyOneAlert) setValidationError("Only one alert is allowed.");
    const atleastOneStep =
      (definition.sequence[0] as SequentialStep)?.sequence.length >= 1;
    if (!atleastOneStep)
      setValidationError("Alert must contain at least one step.");
    const valid = onlyOneAlert && atleastOneStep;
    if (valid) setValidationError(null);
    return valid;
  }

  function stepValidator(
    step: Step | BranchedStep,
    parentSequence: Sequence,
    definition: Definition
  ): boolean {
    if (step.type.includes("condition-")) {
      const onlyActions = (step as BranchedStep).branches.true.every((step) =>
        step.type.includes("action-")
      );
      if (!onlyActions)
        setValidationError("Conditions can only contain actions.");
      const conditionHasActions =
        (step as BranchedStep).branches.true.length > 0;
      if (!conditionHasActions)
        setValidationError("Conditions must contain at least one action.");
      const valid = conditionHasActions && onlyActions;
      if (valid) setValidationError(null);
      return valid;
    }
    if (step.type === "task") {
      const valid = step.name !== "";
      if (!valid) setValidationError("Step name cannot be empty.");
      if (valid) setValidationError(null);
      return valid;
    }
    return true;
  }

  function IconUrlProvider(componentType: string, type: string): string | null {
    if (type === "alert") return "keep.png";
    return `icons/${type
      .replace("step-", "")
      .replace("action-", "")
      .replace("condition-", "")}-icon.png`;
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

  const validatorConfiguration: ValidatorConfiguration = {
    step: stepValidator,
    root: globalValidator,
  };

  const stepsConfiguration: StepsConfiguration = {
    iconUrlProvider: IconUrlProvider,
    canDeleteStep: CanDeleteStep,
    canMoveStep: CanMoveStep,
    isDraggable: IsStepDraggable,
  };

  return (
    <>
      {/* {fileName ? <Title>Current loaded file: {fileName}</Title> : null} */}
      {validationError ? (
        <Callout
          className="mt-4 mb-5"
          title="Validation Error"
          icon={ExclamationCircleIcon}
          color="rose"
        >
          {validationError}
        </Callout>
      ) : (
        <Callout
          className="mt-4 mb-5"
          title="Schema Valid"
          icon={CheckCircleIcon}
          color="teal"
        >
          Alert can be generated successfully
        </Callout>
      )}
      <SequentialWorkflowDesigner
        definition={definition}
        onDefinitionChange={setDefinition}
        stepsConfiguration={stepsConfiguration}
        validatorConfiguration={validatorConfiguration}
        toolboxConfiguration={getToolboxConfiguration(providers)}
        undoStackSize={10}
        controlBar={true}
        globalEditor={<GlobalEditor />}
        stepEditor={<StepEditor />}
      />
    </>
  );
}

export default Builder;
