import "./page.css";
import { useEffect, useState } from "react";
import { Callout, Card } from "@tremor/react";
import { Provider } from "../../providers/providers";
import {
  parseWorkflow,
  generateWorkflow,
  getToolboxConfiguration,
  buildAlert,
  wrapDefinitionV2,
} from "./utils";
import {
  CheckCircleIcon,
  ExclamationCircleIcon,
} from "@heroicons/react/20/solid";
import { globalValidatorV2, stepValidatorV2 } from "./builder-validators";
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
import ReactFlowBuilder from "./ReactFlowBuilder";
import { ReactFlowProvider } from "@xyflow/react";
import useStore, { ReactFlowDefinition, V2Step, Definition as FlowDefinition } from "./builder-store";

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
  isPreview?: boolean;
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
  isPreview,
}: Props) {

  const [definition, setDefinition] = useState(() =>
    wrapDefinitionV2({ sequence: [], properties: {}, isValid: false })
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
  const { setErrorNode } = useStore();

  const setStepValidationErrorV2 = (step: V2Step, error: string | null) => {
    setStepValidationError(error);
    if (error && step) {
      return setErrorNode(step.id)
    }
    setErrorNode(null);
  }

  const setGlobalValidationErrorV2 = (id:string|null, error: string | null) => {
    setGlobalValidationError(error);
    if (error && id) {
      return setErrorNode(id)
    }
    setErrorNode(null);
  }

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
      setDefinition(wrapDefinitionV2({...parseWorkflow(workflow, providers), isValid:true}));
    } else if (loadedAlertFile == null) {
      const alertUuid = uuidv4();
      const alertName = searchParams?.get("alertName");
      const alertSource = searchParams?.get("alertSource");
      let triggers = {};
      if (alertName && alertSource) {
        triggers = { alert: { source: alertSource, name: alertName } };
      }
      setDefinition(
        wrapDefinitionV2({...generateWorkflow(alertUuid, "", "", [], [], triggers), isValid: true})
      );
    } else {
      setDefinition(wrapDefinitionV2({...parseWorkflow(loadedAlertFile!, providers), isValid:true}));
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


  const ValidatorConfigurationV2: {
    step: (step: V2Step,
      parent?: V2Step,
      definition?: ReactFlowDefinition) => boolean;
    root: (def: FlowDefinition) => boolean;
  } = {
    step: (step, parent, definition) =>
      stepValidatorV2(step, setStepValidationErrorV2, parent, definition),
    root: (def) => globalValidatorV2(def, setGlobalValidationErrorV2),
  }

  function closeGenerateModal() {
    setGenerateModalIsOpen(false);
  }

  const closeWorkflowExecutionResultsModal = () => {
    setTestRunModalOpen(false);
    setRunningWorkflowExecution(null);
  };

  const getworkflowStatus = () => {
    return stepValidationError || globalValidationError ? (
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
    );
  };

  return (
    <div className="h-full">
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
          {getworkflowStatus()}
          <div className="h-[94%]">
            <ReactFlowProvider>
              <ReactFlowBuilder
                installedProviders={installedProviders}
                definition={definition}
                validatorConfiguration={ValidatorConfigurationV2}
                onDefinitionChange={(def: any) => {
                  setDefinition({
                    value: {
                      sequence: def?.sequence || [],
                      properties
                        : def?.
                          properties
                        || {}
                    }, isValid: def?.isValid || false
                  })
                }
                }
                toolboxConfiguration={getToolboxConfiguration(providers)}
              />
            </ReactFlowProvider>
          </div>
        </>
      )}
    </div>
  );
}

export default Builder;
