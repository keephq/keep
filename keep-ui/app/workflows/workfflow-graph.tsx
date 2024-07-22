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

Chart.register(
  CategoryScale,
  LinearScale,
  BarElement,
  ChartTitle,
  Tooltip,
  Legend
);

const show_real_data = true;

const demoLabels = [
  "Jan",
  "Feb",
  //  'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov',
  //  'Dec', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
];

const demoData = [
  1, 3,
  // 2, 2, 8, 1, 3, 5, 2,
  // 10, 1, 3, 5, 2, 10
];

const demoBgColors = [
  "rgba(75, 192, 192, 0.2)", // Green
  "rgba(255, 99, 132, 0.2)", // Red
  //   'rgba(75, 192, 192, 0.2)', // Green
  //   'rgba(255, 99, 132, 0.2)', // Red
  //   'rgba(75, 192, 192, 0.2)', // Green
  //   'rgba(255, 99, 132, 0.2)', // Red
  //   'rgba(75, 192, 192, 0.2)', // Green
  //   'rgba(255, 99, 132, 0.2)', // Red
  //   'rgba(75, 192, 192, 0.2)', // Green
  //   'rgba(255, 99, 132, 0.2)', // Red
  //   'rgba(75, 192, 192, 0.2)', // Green
  //   'rgba(255, 99, 132, 0.2)', // Red
  //   'rgba(255, 99, 132, 0.2)', // Red
  //   'rgba(75, 192, 192, 0.2)', // Green
  //   'rgba(255, 99, 132, 0.2)', // Red
];

const demoColors = [
  "rgba(75, 192, 192, 1)", // Green
  "rgba(255, 99, 132, 1)", // Red
  //   'rgba(75, 192, 192, 1)', // Green
  //   'rgba(255, 99, 132, 1)', // Red
  //   'rgba(75, 192, 192, 1)', // Green
  //   'rgba(255, 99, 132, 1)', // Red
  //   'rgba(75, 192, 192, 1)', // Green
  //   'rgba(255, 99, 132, 1)', // Red
  //   'rgba(75, 192, 192, 1)', // Green
  //   'rgba(255, 99, 132, 1)', // Red
  //   'rgba(75, 192, 192, 1)', // Green
  //   'rgba(255, 99, 132, 1)', // Red
  //   'rgba(255, 99, 132, 1)', // Red
  //   'rgba(75, 192, 192, 1)', // Green
  //   'rgba(255, 99, 132, 1)', // Red
];
const getLabels = (
  lastExecutions: Pick<
    WorkflowExecution,
    "execution_time" | "status" | "started"
  >[]
) => {
  if (!lastExecutions || (lastExecutions && lastExecutions.length === 0)) {
    return show_real_data ? [] : demoLabels;
  }
  return lastExecutions?.map((workflowExecution) => {
    return workflowExecution?.started;
  });
};

const getDataValues = (
  lastExecutions: Pick<
    WorkflowExecution,
    "execution_time" | "status" | "started"
  >[]
) => {
  if (!lastExecutions || (lastExecutions && lastExecutions.length === 0)) {
    return show_real_data ? [] : demoData;
  }
  return lastExecutions?.map((workflowExecution) => {
    return (
      workflowExecution?.execution_time ||
      differenceInSeconds(Date.now(), new Date(workflowExecution?.started))
    );
  });
};

const _getColor = (status: string, opacity: number) => {
  if (status === "success") {
    return `rgba(34, 197, 94, ${opacity})`;
  }
  if (["failed", "faliure", "fail", "error"].includes(status)) {
    return `rgba(255, 99, 132, ${opacity})`;
  }

  return `rgba(128, 128, 128, 0.2)`;
};

const getColors = (
  lastExecutions: Pick<
    WorkflowExecution,
    "execution_time" | "status" | "started"
  >[],
  status: string,
  isBgColor?: boolean
) => {
  const opacity = isBgColor ? 0.2 : 1;
  if (!lastExecutions || (lastExecutions && lastExecutions.length === 0)) {
    const tempColors = isBgColor ? [...demoBgColors] : [...demoColors];
    tempColors[tempColors.length - 1] = _getColor(status, opacity);
    return show_real_data ? [] : tempColors;
  }
  return lastExecutions?.map((workflowExecution) => {
    const status = workflowExecution?.status?.toLowerCase();
    return _getColor(status, opacity);
  });
};

function getRandomStatus() {
  const statuses = [
    "success",
    "error",
    "in_progress",
    "providers_not_configured",
  ];
  return statuses[Math.floor(Math.random() * statuses.length)];
}

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

export default function WorkflowGraph({ workflow }: { workflow: Workflow }) {
  const lastExecutions = useMemo(() => {
    const reversedExecutions = workflow?.last_executions?.slice(0, 15) || [];
    return reversedExecutions.reverse();
  }, [workflow?.last_executions]);

  const hasNoData = !lastExecutions || lastExecutions.length === 0;
  let status = workflow?.last_execution_status?.toLowerCase() || "";
  status = hasNoData ? getRandomStatus() : status;

  const chartData = {
    labels: getLabels(lastExecutions),
    datasets: [
      {
        label: "Execution Time (mins)",
        data: getDataValues(lastExecutions),
        backgroundColor: getColors(lastExecutions, status, true),
        borderColor: getColors(lastExecutions, status),
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
      <div className="overflow-hidden h-32 w-full flex-shrink-1">
        <Bar data={chartData} options={chartOptions} />
      </div>
    </div>
  );
}
