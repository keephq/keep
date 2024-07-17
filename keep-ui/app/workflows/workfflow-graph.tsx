import { CheckCircleIcon, XCircleIcon } from "@heroicons/react/24/outline";
import { line } from "d3-shape";
import { useMemo } from "react";
import Image from "next/image";
import { Chart, CategoryScale, LinearScale, BarElement, Title as ChartTitle, Tooltip, Legend } from 'chart.js';
import { Bar } from 'react-chartjs-2';
import 'chart.js/auto';
import { Workflow, WorkflowExecution } from "./models";
import { differenceInSeconds } from "date-fns";
import { Card } from "@tremor/react";
import { wrap } from "module";

Chart.register(CategoryScale, LinearScale, BarElement, ChartTitle, Tooltip, Legend);


const show_real_data = false

const demoLabels = ['Jan', 'Feb',
    //  'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov',
    //  'Dec', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
    ];
const demoData = [1, 3, 
    // 2, 2, 8, 1, 3, 5, 2, 
    // 10, 1, 3, 5, 2, 10
]

const demoBgColors = [
  'rgba(75, 192, 192, 0.2)', // Green
  'rgba(255, 99, 132, 0.2)', // Red
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
]

const demoColors = [
  'rgba(75, 192, 192, 1)', // Green
  'rgba(255, 99, 132, 1)', // Red
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

export default function WorkflowGraph({ workflow }:{workflow: Workflow}){
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
        barPercentage: 0.5, // Adjust this value to control bar width
        // categoryPercentage: 0.7, // Adjust this value to control space between bars
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

  let icon =  (
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
      icon = <XCircleIcon className="size-6 cover text-red-500" />;
      break;
    default:
      break;
  }

  return (
    <div className="container">
      <div className="flex items-center">{(!hasNoData || !show_real_data) && icon}</div>
      <div>
        {hasNoData && show_real_data ? (
          <div className="flex justify-center items-center text-gray-400">
            No data available
          </div>
        ) : (
          <div className="overflow-hidden h-24">
            <Bar data={chartData} options={chartOptions} />
          </div>
        )}
      </div>
    </div>
  );
};