"use client";

import { useSession } from "next-auth/react";
import { Workflow, Filter } from './models';
import { getApiURL } from "../../utils/apiUrl";
import Image from "next/image";
import React, { useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import WorkflowMenu from "./workflow-menu";
import Loading from "../loading";
import { Trigger, Provider } from "./models";
import {
  Button,
  Text,
  Card,
  Title,
  Icon,
  ListItem,
  List,
  Accordion,
  AccordionBody,
  AccordionHeader,
  Badge,
} from "@tremor/react";
import ProviderForm from "app/providers/provider-form";
import SlidingPanel from "react-sliding-side-panel";
import { useFetchProviders } from "app/providers/page.client";
import { Provider as FullProvider } from "app/providers/providers";
import "./workflow-tile.css";
import { CheckCircleIcon, XCircleIcon } from "@heroicons/react/24/outline";
import AlertTriggerModal from "./workflow-run-with-alert-modal";
import { parseISO, set, differenceInSeconds } from "date-fns";
import { Chart, CategoryScale, LinearScale, BarElement, Title as ChartTitle, Tooltip, Legend } from 'chart.js';
import { Bar } from 'react-chartjs-2';
import 'chart.js/auto';
import TimeAgo from 'react-timeago';
import { WorkflowExecution } from "./builder/types";



Chart.register(CategoryScale, LinearScale, BarElement, ChartTitle, Tooltip, Legend);


function WorkflowMenuSection({
  onDelete,
  onRun,
  onDownload,
  onView,
  onBuilder,
  workflow,
}: {
  onDelete: () => Promise<void>;
  onRun: () => Promise<void>;
  onDownload: () => void;
  onView: () => void;
  onBuilder: () => void;
  workflow: Workflow;
}) {
  // Determine if all providers are installed
  const allProvidersInstalled = workflow.providers.every(
    (provider) => provider.installed
  );

  // Check if there is a manual trigger
  const hasManualTrigger = workflow.triggers.some(
    (trigger) => trigger.type === "manual"
  ); // Replace 'manual' with the actual value that represents a manual trigger in your data

  const hasAlertTrigger = workflow.triggers.some(
    (trigger) => trigger.type === "alert"
  );

  return (
    <WorkflowMenu
      onDelete={onDelete}
      onRun={onRun}
      onDownload={onDownload}
      onView={onView}
      onBuilder={onBuilder}
      allProvidersInstalled={allProvidersInstalled}
      hasManualTrigger={hasManualTrigger}
      hasAlertTrigger={hasAlertTrigger}
    />
  );
}

function TriggerTile({ trigger }: { trigger: Trigger }) {
  return (
    <ListItem>
      <span className="text-sm">{trigger.type}</span>
      {trigger.type === "manual" && (
        <span>
          <Icon icon={CheckCircleIcon} color="green" size="xs" />
        </span>
      )}
      {trigger.type === "interval" && <span>{trigger.value} seconds</span>}
      {trigger.type === "alert" && (
        <span className="text-sm text-right">
          {trigger.filters &&
            trigger.filters.map((filter) => (
              <>
                {filter.key} = {filter.value}
                <br />
              </>
            ))}
        </span>
      )}
    </ListItem>
  );
}

function ProviderTile({
  provider,
  onConnectClick,
}: {
  provider: FullProvider;
  onConnectClick: (provider: FullProvider) => void;
}) {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <div
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      className={`relative group flex flex-col justify-around items-center bg-white rounded-lg w-24 h-28 mt-2.5 mr-2.5 hover:grayscale-0 shadow-md hover:shadow-lg`}
      title={`${provider.details.name} (${provider.type})`}
    >
      {provider.installed ? (
        <Icon
          icon={CheckCircleIcon}
          className="absolute top-[-15px] right-[-15px]"
          color="green"
          size="sm"
          tooltip="Connected"
        />
      ) : (
        <Icon
          icon={XCircleIcon}
          className="absolute top-[-15px] right-[-15px]"
          color="red"
          size="sm"
          tooltip="Disconnected"
        />
      )}
      <Image
        src={`/icons/${provider.type}-icon.png`}
        width={30}
        height={30}
        alt={provider.type}
        className={`${provider.installed ? "mt-6" : "mt-6 grayscale group-hover:grayscale-0"
          }`}
      />

      <div className="h-8 w-[70px] flex justify-center">
        {!provider.installed && isHovered ? (
          <Button
            variant="secondary"
            size="xs"
            color="green"
            onClick={() => onConnectClick(provider)}
          >
            Connect
          </Button>
        ) : (
          <p className="text-tremor-default text-tremor-content dark:text-dark-tremor-content truncate">
            {provider.details.name}
          </p>
        )}
      </div>
    </div>
  );
}

function WorkflowTile({ workflow }: { workflow: Workflow }) {
  // Create a set to keep track of unique providers
  const apiUrl = getApiURL();
  const { data: session } = useSession();
  const router = useRouter();
  const [openPanel, setOpenPanel] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<FullProvider | null>(
    null
  );
  const [formValues, setFormValues] = useState<{ [key: string]: string }>({});
  const [formErrors, setFormErrors] = useState<{ [key: string]: string }>({});
  const [isRunning, setIsRunning] = useState(false);
  const [isAlertTriggerModalOpen, setIsAlertTriggerModalOpen] = useState(false);

  const [alertFilters, setAlertFilters] = useState<Filter[]>([]);
  const [alertDependencies, setAlertDependencies] = useState<string[]>([]);

  const { providers } = useFetchProviders();

  const handleConnectProvider = (provider: FullProvider) => {
    setSelectedProvider(provider);
    // prepopulate it with the name
    setFormValues({ provider_name: provider.details.name || "" });
    setOpenPanel(true);
  };

  const handleCloseModal = () => {
    setOpenPanel(false);
    setSelectedProvider(null);
    setFormValues({});
    setFormErrors({});
  };
  // Function to handle form change
  const handleFormChange = (
    updatedFormValues: Record<string, string>,
    updatedFormErrors: Record<string, string>
  ) => {
    setFormValues(updatedFormValues);
    setFormErrors(updatedFormErrors);
  };

  // todo: this logic should move to the backend
  function extractAlertDependencies(workflowRaw: string): string[] {
    const dependencyRegex = /(?<!if:.*?)(\{\{\s*alert\.[\w.]+\s*\}\})/g;
    const dependencies = workflowRaw.match(dependencyRegex);

    if (!dependencies) {
      return [];
    }

    // Convert Set to Array
    const uniqueDependencies = Array.from(new Set(dependencies)).reduce<
      string[]
    >((acc, dep) => {
      // Ensure 'dep' is treated as a string
      const match = dep.match(/alert\.([\w.]+)/);
      if (match) {
        acc.push(match[1]);
      }
      return acc;
    }, []);

    return uniqueDependencies;
  }

  const runWorkflow = async (payload: object) => {
    try {
      setIsRunning(true);
      const response = await fetch(`${apiUrl}/workflows/${workflow.id}/run`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session?.accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (response.ok) {
        // Workflow started successfully
        const responseData = await response.json();
        const { workflow_execution_id } = responseData;
        setIsRunning(false);
        router.push(`/workflows/${workflow.id}/runs/${workflow_execution_id}`);
      } else {
        console.error("Failed to start workflow");
      }
    } catch (error) {
      console.error("An error occurred while starting workflow", error);
    }
    setIsRunning(false);
  };

  const handleRunClick = async () => {
    const hasAlertTrigger = workflow.triggers.some(
      (trigger) => trigger.type === "alert"
    );

    // if it needs alert payload, than open the modal
    if (hasAlertTrigger) {
      // extract the filters
      // TODO: support more than one trigger
      for (const trigger of workflow.triggers) {
        // at least one trigger is alert, o/w hasAlertTrigger was false
        if (trigger.type === "alert") {
          const staticAlertFilters = trigger.filters || [];
          setAlertFilters(staticAlertFilters);
          break;
        }
      }
      const dependencies = extractAlertDependencies(workflow.workflow_raw);
      setAlertDependencies(dependencies);
      setIsAlertTriggerModalOpen(true);
      return;
    }
    // else, manual trigger, just run it
    else {
      runWorkflow({});
    }
  };

  const handleAlertTriggerModalSubmit = (payload: any) => {
    runWorkflow(payload); // Function to run the workflow with the payload
  };

  const handleDeleteClick = async () => {
    try {
      const response = await fetch(`${apiUrl}/workflows/${workflow.id}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${session?.accessToken}`,
        },
      });

      if (response.ok) {
        // Workflow deleted successfully
        window.location.reload();
      } else {
        console.error("Failed to delete workflow");
      }
    } catch (error) {
      console.error("An error occurred while deleting workflow", error);
    }
  };

  const handleConnecting = (isConnecting: boolean, isConnected: boolean) => {
    if (isConnected) {
      handleCloseModal();
      // refresh the page to show the changes
      window.location.reload();
    }
  };
  const handleDownloadClick = async () => {
    try {
      // Use the raw workflow data directly, as it is already in YAML format
      const workflowYAML = workflow.workflow_raw;

      // Create a Blob object representing the data as a YAML file
      const blob = new Blob([workflowYAML], { type: "text/yaml" });

      // Create an anchor element with a URL object created from the Blob
      const url = window.URL.createObjectURL(blob);

      // Create a "hidden" anchor tag with the download attribute and click it
      const a = document.createElement("a");
      a.style.display = "none";
      a.href = url;
      a.download = `${workflow.workflow_raw_id}.yaml`; // The file will be named after the workflow's id
      document.body.appendChild(a);
      a.click();

      // Release the object URL to free up resources
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error("An error occurred while downloading the YAML", error);
    }
  };

  const handleViewClick = async () => {
    router.push(`/workflows/${workflow.id}`);
  };

  const handleBuilderClick = async () => {
    router.push(`/workflows/builder/${workflow.id}`);
  };

  const workflowProvidersMap = new Map(
    workflow.providers.map((p) => [p.type, p])
  );

  const uniqueProviders: FullProvider[] = Array.from(
    new Set(workflow.providers.map((p) => p.type))
  )
    .map((type) => {
      let fullProvider =
        providers.find((fp) => fp.type === type) || ({} as FullProvider);
      let workflowProvider =
        workflowProvidersMap.get(type) || ({} as FullProvider);

      // Merge properties
      const mergedProvider: FullProvider = {
        ...fullProvider,
        ...workflowProvider,
        installed: workflowProvider.installed || fullProvider.installed,
        details: {
          authentication: {},
          name: (workflowProvider as Provider).name || fullProvider.id,
        },
        id: fullProvider.type,
      };

      return mergedProvider;
    })
    .filter(Boolean) as FullProvider[];
  const triggerTypes = workflow.triggers.map((trigger) => trigger.type);
  return (
    <div className="mt-2.5 flex flex-wrap gap-4 items-start">
      {isRunning && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <Loading />
        </div>
      )}
      <div className="relative flex flex-col bg-white rounded overflow-hidden shadow w-full lg:max-w-md">
        <div className="absolute top-0 right-0 mt-2 mr-2 mb-2">
          {WorkflowMenuSection({
            onDelete: handleDeleteClick,
            onRun: handleRunClick,
            onDownload: handleDownloadClick,
            onView: handleViewClick,
            onBuilder: handleBuilderClick,
            workflow,
          })}
        </div>
        <div className="m-4">
          <WorkflowGraph workflow={workflow} />
          <div className="flex flex-col mt-2 gap-2">
            <h2 className="truncate leading-6 font-bold text-base md:text-lg lg:text-xl">{workflow?.name || 'Unknown'}</h2>
            <div className="flex flex-col md:flex-row md:items-center justify-between w-full gap-2">
              <div className="flex flex-wrap justify-start items-center gap-1.5">
                <button className="border border-gray-200 text-black py-1 px-3 text-xs rounded-full hover:bg-gray-100 font-bold">
                  Interval
                </button>
                <button className="bg-white border border-gray-200 text-black py-1 px-3 text-xs rounded-full hover:bg-gray-100 font-bold">
                  Trigger
                </button>
              </div>
              {workflow && workflow.last_execution_started ? (
                <TimeAgo date={workflow?.last_execution_started + 'Z'} className="text-sm text-gray-500" />
              ) : null
              }
            </div>
          </div>
        </div>
      </div>

      <AlertTriggerModal
        isOpen={isAlertTriggerModalOpen}
        onClose={() => setIsAlertTriggerModalOpen(false)}
        onSubmit={handleAlertTriggerModalSubmit}
        staticFields={alertFilters}
        dependencies={alertDependencies}
      />
    </div>
  );
}


const show_real_data = true

const demoLabels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const demoData = [1, 3, 2, 2, 8, 1, 3, 5, 2, 10, 1, 3, 5, 2, 10]

const demoBgColors = [
  'rgba(75, 192, 192, 0.2)', // Green
  'rgba(255, 99, 132, 0.2)', // Red
  'rgba(75, 192, 192, 0.2)', // Green
  'rgba(255, 99, 132, 0.2)', // Red
  'rgba(75, 192, 192, 0.2)', // Green
  'rgba(255, 99, 132, 0.2)', // Red
  'rgba(75, 192, 192, 0.2)', // Green
  'rgba(255, 99, 132, 0.2)', // Red
  'rgba(75, 192, 192, 0.2)', // Green
  'rgba(255, 99, 132, 0.2)', // Red
  'rgba(75, 192, 192, 0.2)', // Green
  'rgba(255, 99, 132, 0.2)', // Red
  'rgba(255, 99, 132, 0.2)', // Red
  'rgba(75, 192, 192, 0.2)', // Green
  'rgba(255, 99, 132, 0.2)', // Red
]

const demoColors = [
  'rgba(75, 192, 192, 1)', // Green
  'rgba(255, 99, 132, 1)', // Red
  'rgba(75, 192, 192, 1)', // Green
  'rgba(255, 99, 132, 1)', // Red
  'rgba(75, 192, 192, 1)', // Green
  'rgba(255, 99, 132, 1)', // Red
  'rgba(75, 192, 192, 1)', // Green
  'rgba(255, 99, 132, 1)', // Red
  'rgba(75, 192, 192, 1)', // Green
  'rgba(255, 99, 132, 1)', // Red
  'rgba(75, 192, 192, 1)', // Green
  'rgba(255, 99, 132, 1)', // Red
  'rgba(255, 99, 132, 1)', // Red
  'rgba(75, 192, 192, 1)', // Green
  'rgba(255, 99, 132, 1)', // Red
]
const getLabels = (lastExecutions: Pick<WorkflowExecution, 'execution_time' | 'status' | 'started'>[]) => {
  if (!lastExecutions || (lastExecutions && lastExecutions.length === 0)) {
    return show_real_data ? [] : demoLabels;
  }
  return lastExecutions?.map((workflowExecution) => {
    return workflowExecution?.started
  })
}


const getDataValues = (lastExecutions: Pick<WorkflowExecution, 'execution_time' | 'status' | 'started'>[]) => {
  if (!lastExecutions || (lastExecutions && lastExecutions.length === 0)) {
    return show_real_data ? [] : demoData;
  }
  return lastExecutions?.map((workflowExecution) => {
    return workflowExecution?.execution_time || differenceInSeconds(Date.now(),  new Date(workflowExecution?.started));
  })
}


const getBackgroundColors = (lastExecutions: Pick<WorkflowExecution, 'execution_time' | 'status' | 'started'>[]) => {
  if (!lastExecutions || (lastExecutions && lastExecutions.length === 0)) {
    return show_real_data ? [] : demoBgColors;
  }
  return lastExecutions?.map((workflowExecution) => {
    const status = workflowExecution?.status?.toLowerCase()
    if (status === "success") {
      return "rgba(75, 192, 192, 0.2)"
    }
    if (['failed', 'faliure'].includes(status)) {
      return 'rgba(255, 99, 132, 0.2)'
    }

    return "rgba(75, 192, 192, 0.2)"
  })
}

const getBorderColors = (lastExecutions: Pick<WorkflowExecution, 'execution_time' | 'status' | 'started'>[]) => {
  if (!lastExecutions || (lastExecutions && lastExecutions.length === 0)) {
    return show_real_data ? [] : demoColors;
  }

  return lastExecutions?.map((workflowExecution) => {
    const status = workflowExecution?.status?.toLowerCase()
    if (status === "success") {
      return "rgba(75, 192, 192, 1)"
    }
    if (['failed', 'faliure', 'fail'].includes(status)) {
      return 'rgba(255, 99, 132, 1)'
    }

    return "rgba(75, 192, 192, 1)"
  })
}

const WorkflowGraph = ({ workflow }:{workflow: Workflow}) => {
  const lastExecutions = useMemo(() => {
    const reversedExecutions = workflow?.last_executions?.slice(0, 15) || [];
    return reversedExecutions.reverse();
  }, [workflow?.last_executions]);

  const hasNoData = !lastExecutions || lastExecutions.length === 0;

  const chartData = {
    labels: getLabels(lastExecutions),
    datasets: [
      {
        label: "Execution Time (mins)",
        data: getDataValues(lastExecutions),
        backgroundColor: getBackgroundColors(lastExecutions),
        borderColor: getBorderColors(lastExecutions),
        borderWidth: {
                    top: 2,
                    right: 0,
                    bottom: 0,
                    left: 0,
                  },
        barPercentage: 1, // Adjust this value to control bar width
        categoryPercentage: 0.5, // Adjust this value to control space between bars
      },
    ],
  };

  const chartOptions = {
    scales: {
      x: {
        beginAtZero: true,
        ticks: {
          display: false,
        },
        grid: {
          display: false,
        },
        border: {
          display: false,
        },
      },
      y: {
        beginAtZero: true,
        ticks: {
          display: false,
        },
        grid: {
          display: false,
        },
        border: {
          display: false,
        },
      },
    },
    plugins: {
      legend: {
        display: false,
      },
    },
    responsive: true,
    maintainAspectRatio: false,
  };

  const status = workflow?.last_execution_status?.toLowerCase() || null;

  let icon = (
    <Image
      className="animate-bounce"
      src="/keep.svg"
      alt="loading"
      width={40}
      height={40}
    />
  );
  switch (status) {
    case "success":
      icon = <CheckCircleIcon className="w-6 h-6 text-green-500" />;
      break;
    case "failed":
    case "fail":
    case "failure":
      icon = <XCircleIcon className="w-6 h-6 text-red-500" />;
      break;
    default:
      break;
  }

  return (
    <div className="flex flex-row items-center">
      <div className="mr-2">{!hasNoData && icon}</div>
      <div className="flex-grow h-24">
        {hasNoData ? (
          <div className="flex justify-center items-center h-full text-gray-400">
            No data available
          </div>
        ) : (
          <div className="h-full w-full overflow-hidden">
            <Bar data={chartData} options={chartOptions} />
          </div>
        )}
      </div>
    </div>
  );
};


export default WorkflowTile;
