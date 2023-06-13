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
} from "sequential-workflow-designer";
import {
  SequentialWorkflowDesigner,
  wrapDefinition,
} from "sequential-workflow-designer-react";
import { useEffect, useState } from "react";
import StepEditor, { GlobalEditor } from "./editors";
import { Callout } from "@tremor/react";
import { Provider } from "../providers/providers";
import {
  parseAlert,
  generateAlert,
  getToolboxConfiguration,
  buildAlert,
} from "./utils";
import {
  CheckCircleIcon,
  ExclamationCircleIcon,
} from "@heroicons/react/20/solid";
import { globalValidator, stepValidator } from "./builder-validators";

interface Props {
  loadedAlertFile: string | null;
  fileName: string;
  providers: Provider[];
  enableGenerate: (status: boolean) => void;
  triggerGenerate: number;
}

function Builder({
  loadedAlertFile,
  fileName,
  providers,
  enableGenerate,
  triggerGenerate,
}: Props) {
  const [definition, setDefinition] = useState(() =>
    wrapDefinition({ sequence: [], properties: {} } as Definition)
  );
  const [stepValidationError, setStepValidationError] = useState<string | null>(
    null
  );
  const [globalValidationError, setGlobalValidationError] = useState<
    string | null
  >(null);

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

  useEffect(() => {
    if (triggerGenerate) {
      buildAlert(definition.value);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [triggerGenerate]);

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
    step: (step, parent, definition) =>
      stepValidator(step, parent, definition, setStepValidationError),
    root: (def) => globalValidator(def, setGlobalValidationError),
  };

  const stepsConfiguration: StepsConfiguration = {
    iconUrlProvider: IconUrlProvider,
    canDeleteStep: CanDeleteStep,
    canMoveStep: CanMoveStep,
    isDraggable: IsStepDraggable,
  };

  enableGenerate(definition.isValid || false);

  return (
    <>
      {/* {fileName ? <Title>Current loaded file: {fileName}</Title> : null} */}
      {stepValidationError || globalValidationError ? (
        <Callout
          className="mt-2.5 mb-2.5"
          title="Validation Error"
          icon={ExclamationCircleIcon}
          color="rose"
        >
          {stepValidationError || globalValidationError}
        </Callout>
      ) : (
        <Callout
          className="mt-2.5 mb-2.5"
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
