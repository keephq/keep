import { differenceInSeconds } from "date-fns";
import { LastWorkflowExecution } from "@/shared/api/workflows";

const demoLabels = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

const demoData = [1, 3, 2, 2, 8, 1, 3, 5, 2, 10, 1, 3, 5, 2, 10];

const demoBgColors = [
  "rgba(75, 192, 192, 0.2)", // Green
  "rgba(255, 99, 132, 0.2)", // Red
  "rgba(75, 192, 192, 0.2)", // Green
  "rgba(255, 99, 132, 0.2)", // Red
  "rgba(75, 192, 192, 0.2)", // Green
  "rgba(255, 99, 132, 0.2)", // Red
  "rgba(75, 192, 192, 0.2)", // Green
  "rgba(255, 99, 132, 0.2)", // Red
  "rgba(75, 192, 192, 0.2)", // Green
  "rgba(255, 99, 132, 0.2)", // Red
  "rgba(75, 192, 192, 0.2)", // Green
  "rgba(255, 99, 132, 0.2)", // Red
  "rgba(255, 99, 132, 0.2)", // Red
  "rgba(75, 192, 192, 0.2)", // Green
  "rgba(255, 99, 132, 0.2)", // Red
];

const demoColors = [
  "rgba(75, 192, 192, 1)", // Green
  "rgba(255, 99, 132, 1)", // Red
  "rgba(75, 192, 192, 1)", // Green
  "rgba(255, 99, 132, 1)", // Red
  "rgba(75, 192, 192, 1)", // Green
  "rgba(255, 99, 132, 1)", // Red
  "rgba(75, 192, 192, 1)", // Green
  "rgba(255, 99, 132, 1)", // Red
  "rgba(75, 192, 192, 1)", // Green
  "rgba(255, 99, 132, 1)", // Red
  "rgba(75, 192, 192, 1)", // Green
  "rgba(255, 99, 132, 1)", // Red
  "rgba(255, 99, 132, 1)", // Red
  "rgba(75, 192, 192, 1)", // Green
  "rgba(255, 99, 132, 1)", // Red
];
export const getLabels = (
  lastExecutions: LastWorkflowExecution[],
  show_real_data?: boolean
) => {
  if (!lastExecutions || (lastExecutions && lastExecutions.length === 0)) {
    return show_real_data ? [] : demoLabels;
  }
  return lastExecutions?.map((workflowExecution) => {
    let started = workflowExecution?.started
      ? new Date(workflowExecution?.started + "Z").toLocaleString()
      : "N/A";
    return `${started}(${workflowExecution.status})`;
  });
};

export const getDataValues = (
  lastExecutions: LastWorkflowExecution[],
  show_real_data?: boolean
) => {
  if (!lastExecutions || (lastExecutions && lastExecutions.length === 0)) {
    return show_real_data ? [] : demoData;
  }
  return lastExecutions?.map((workflowExecution) => {
    return (
      workflowExecution?.execution_time ||
      differenceInSeconds(
        new Date(Date.now().toLocaleString()),
        new Date(new Date(workflowExecution?.started + "Z").toLocaleString())
      )
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

export const getColors = (
  lastExecutions: LastWorkflowExecution[],
  status: string,
  isBgColor?: boolean,
  show_real_data?: boolean
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

export function getRandomStatus() {
  const statuses = [
    "success",
    "error",
    "in_progress",
    "timeout",
    "providers_not_configured",
  ];
  return statuses[Math.floor(Math.random() * statuses.length)];
}

export const chartOptions = {
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
