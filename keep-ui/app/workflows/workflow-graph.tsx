import { CheckCircleIcon, XCircleIcon } from "@heroicons/react/24/outline";
import { useMemo } from "react";
import Image from "next/image";
import {
  Chart,
  CategoryScale,
  LinearScale,
  BarElement,
  Title as ChartTitle,
  Tooltip,
  Legend,
} from "chart.js";
import { Bar } from "react-chartjs-2";
import "chart.js/auto";
import { Workflow, WorkflowExecution } from "./models";
import { differenceInSeconds } from "date-fns";
import { useRouter } from "next/navigation";
import {
  getRandomStatus,
  getLabels,
  getDataValues,
  getColors,
  chartOptions,
} from "./workflowutils";

Chart.register(
  CategoryScale,
  LinearScale,
  BarElement,
  ChartTitle,
  Tooltip,
  Legend
);

const show_real_data = false;

export default function WorkflowGraph({ workflow }: { workflow: Workflow }) {
  const router = useRouter();
  const lastExecutions = useMemo(() => {
    let executions =
      workflow?.last_executions?.slice(0, 15) || [];
    //as discussed making usre if all the executions are providers_not_configured. thne ignoring it
    const providerNotConfiguredExecutions = executions.filter(
      (execution) => execution?.status === "providers_not_configured"
    );
    return providerNotConfiguredExecutions.length == executions.length
      ? []
      : executions.reverse();
  }, [workflow?.last_executions]);

  const hasNoData = !lastExecutions || lastExecutions.length === 0;
  let status = workflow?.last_execution_status?.toLowerCase() || "";
  status = hasNoData ? getRandomStatus() : status;

  const chartData = {
    labels: getLabels(lastExecutions),
    datasets: [
      {
        label: "Execution Time (seconds)",
        data: getDataValues(lastExecutions, show_real_data),
        backgroundColor: getColors(
          lastExecutions,
          status,
          true,
          show_real_data
        ),
        borderColor: getColors(lastExecutions, status, false, show_real_data),
        borderWidth: {
          top: 2,
          right: 0,
          bottom: 0,
          left: 0,
        },
        barPercentage: 0.6, // Adjust this value to control bar width
        // categoryPercentage: 0.7, // Adjust this value to control space between bars
      },
    ],
  };
  function getIcon() {
    if (show_real_data && hasNoData) {
      return null;
    }

    let icon = (
      <Image
        className="animate-bounce size-6 cover"
        src="/keep.svg"
        alt="loading"
        width={40}
        height={40}
      />
    );
    switch (status) {
      case "success":
        icon = <CheckCircleIcon className="size-6 cover text-green-500" />;
        break;
      case "failed":
      case "fail":
      case "failure":
      case "error":
        icon = <XCircleIcon className="size-6 cover text-red-500" />;
        break;
      case "in_progress":
        icon = <div className="loader"></div>;
        break;
      default:
        icon = <div className="loader"></div>;
    }
    return icon;
  }
  if (hasNoData && show_real_data) {
    return (
      <div className="flex justify-center items-center text-gray-400 h-36">
        No data available
      </div>
    );
  }

  return (
    <div className="flex felx-row items-end justify-start h-36 flex-nowrap w-full">
      <div>{getIcon()}</div>
      <div
        className="overflow-hidden h-32 w-full flex-shrink-1"
        onClick={() => {
          router.push(`/workflows/${workflow.id}`);
        }}
      >
        <Bar data={chartData} options={chartOptions} />
      </div>
    </div>
  );
}
