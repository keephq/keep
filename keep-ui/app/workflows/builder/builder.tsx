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
import { Callout, Card } from "@tremor/react";
import { Provider } from "../../providers/providers";
import {
  parseWorkflow,
  generateWorkflow,
  getToolboxConfiguration,
  buildAlert,
} from "./utils";
import {
  CheckCircleIcon,
  ExclamationCircleIcon,
} from "@heroicons/react/20/solid";
import { globalValidator, stepValidator } from "./builder-validators";
import Modal from "react-modal";
import { Alert } from "./alert";
import BuilderModalContent from "./builder-modal";
import { getApiURL } from "utils/apiUrl";
import Loader from "./loader";
import { stringify } from "yaml";
import { useSearchParams } from "next/navigation";
import { v4 as uuidv4 } from "uuid";
import BuilderWorkflowTestRunModalContent from "./builder-workflow-testrun-modal";
import { WorkflowExecution, WorkflowExecutionFailure } from "./types";

interface Props {
  loadedAlertFile: string | null;
  fileName: string;
  providers: Provider[];
  enableGenerate: (status: boolean) => void;
  triggerGenerate: number;
  triggerSave: number;
  triggerRun: number;
  workflow?: string;
  workflowId?: string;
  accessToken?: string;
  installedProviders?: Provider[] | undefined | null;
}

function Builder({
  loadedAlertFile,
  fileName,
  providers,
  enableGenerate,
  triggerGenerate,
  triggerSave,
  triggerRun,
  workflow,
  workflowId,
  accessToken,
  installedProviders,
}: Props) {
  const [definition, setDefinition] = useState(() =>
    wrapDefinition({ sequence: [], properties: {} } as Definition)
  );
  const [isLoading, setIsLoading] = useState(true);
  const [stepValidationError, setStepValidationError] = useState<string | null>(
    null
  );
  const [globalValidationError, setGlobalValidationError] = useState<
    string | null
  >(null);
  const [generateModalIsOpen, setGenerateModalIsOpen] = useState(false);
  const [testRunModalOpen, setTestRunModalOpen] = useState(false);
  const [runningWorkflowExecution, setRunningWorkflowExecution] = useState<
    WorkflowExecution | WorkflowExecutionFailure | null
  >(null);
  const [compiledAlert, setCompiledAlert] = useState<Alert | null>(null);

  const searchParams = useSearchParams();

  const updateWorkflow = () => {
    const apiUrl = getApiURL();
    const url = `${apiUrl}/workflows/${workflowId}`;
    const method = "PUT";
    const headers = {
      "Content-Type": "text/html",
      Authorization: `Bearer ${accessToken}`,
    };
    const body = stringify(buildAlert(definition.value));
    fetch(url, { method, headers, body })
      .then((response) => {
        if (response.ok) {
          window.location.assign("/workflows");
        } else {
          throw new Error(response.statusText);
        }
      })
      .catch((error) => {
        alert(`Error: ${error}`);
      });
  };

  const testRunWorkflow = () => {
    const apiUrl = getApiURL();
    const url = `${apiUrl}/workflows/test`;
    const method = "POST";
    const headers = {
      "Content-Type": "text/html",
      Authorization: `Bearer ${accessToken}`,
    };

    setTestRunModalOpen(true);
    const body = stringify(buildAlert(definition.value));
    fetch(url, { method, headers, body })
      .then((response) => {
        if (response.ok) {
          response.json().then((data) => {
            setRunningWorkflowExecution({
              ...data,
            });
          });
        } else {
          response.json().then((data) => {
            setRunningWorkflowExecution({
              error: data?.detail ?? "Unknown error",
            });
          });
        }
      })
      .catch((error) => {
        alert(`Error: ${error}`);
        setTestRunModalOpen(false);
      });
  };

  const addWorkflow = () => {
    const apiUrl = getApiURL();
    const url = `${apiUrl}/workflows/json`;
    const method = "POST";
    const headers = {
      "Content-Type": "text/html",
      Authorization: `Bearer ${accessToken}`,
    };
    const body = stringify(buildAlert(definition.value));
    fetch(url, { method, headers, body })
      .then((response) => {
        if (response.ok) {
          // This is important because it makes sure we will re-fetch the workflow if we get to this page again.
          // router.push for instance, optimizes re-render of same pages and we don't want that here because of "cache".
          window.location.assign("/workflows");
        } else {
          throw new Error(response.statusText);
        }
      })
      .catch((error) => {
        alert(`Error: ${error}`);
      });
  };

  useEffect(() => {
    setIsLoading(true);
    if (workflow) {
      setDefinition(wrapDefinition(parseWorkflow(workflow, providers)));
    } else if (loadedAlertFile == null) {
      const alertUuid = uuidv4();
      const alertName = searchParams?.get("alertName");
      const alertSource = searchParams?.get("alertSource");
      let triggers = {};
      if (alertName && alertSource) {
        triggers = { alert: { source: alertSource, name: alertName } };
      }
      setDefinition(
        wrapDefinition(generateWorkflow(alertUuid, "", "", [], [], triggers))
      );
    } else {
      setDefinition(wrapDefinition(parseWorkflow(loadedAlertFile!, providers)));
    }
    setIsLoading(false);
  }, [loadedAlertFile, workflow, searchParams]);

  useEffect(() => {
    if (triggerGenerate) {
      setCompiledAlert(buildAlert(definition.value));
      if (!generateModalIsOpen) setGenerateModalIsOpen(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [triggerGenerate]);

  useEffect(() => {
    if (triggerRun) {
      testRunWorkflow();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [triggerRun]);

  useEffect(() => {
    if (triggerSave) {
      if (workflowId) {
        updateWorkflow();
      } else {
        addWorkflow();
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [triggerSave]);

  useEffect(() => {
    enableGenerate(
      (definition.isValid &&
        stepValidationError === null &&
        globalValidationError === null) ||
        false
    );
  }, [
    stepValidationError,
    globalValidationError,
    enableGenerate,
    definition.isValid,
  ]);

  if (isLoading) {
    return (
      <Card className={`p-4 md:p-10 mx-auto max-w-7xl mt-6`}>
        <Loader />
      </Card>
    );
  }

  function IconUrlProvider(componentType: string, type: string): string | null {
    if (type === "alert" || type === "workflow") return "/keep.png";
    return `/icons/${type
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

  function closeGenerateModal() {
    setGenerateModalIsOpen(false);
  }

  const closeWorkflowExecutionResultsModal = () => {
    setTestRunModalOpen(false);
    setRunningWorkflowExecution(null);
  };

  return (
    <>
      <Modal
        onRequestClose={closeGenerateModal}
        isOpen={generateModalIsOpen}
        className="bg-gray-50 p-4 md:p-10 mx-auto max-w-7xl mt-20 border border-orange-600/50 rounded-md"
      >
        <BuilderModalContent
          closeModal={closeGenerateModal}
          compiledAlert={compiledAlert}
        />
      </Modal>
      <Modal
        isOpen={testRunModalOpen}
        onRequestClose={closeWorkflowExecutionResultsModal}
        className="bg-gray-50 p-4 md:p-10 mx-auto max-w-7xl mt-20 border border-orange-600/50 rounded-md"
      >
        <BuilderWorkflowTestRunModalContent
          closeModal={closeWorkflowExecutionResultsModal}
          workflowExecution={runningWorkflowExecution}
        />
      </Modal>
      {generateModalIsOpen || testRunModalOpen ? null : (
        <>
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
            stepEditor={<StepEditor installedProviders={installedProviders} />}
          />
        </>
      )}
    </>
  );
}

export default Builder;
