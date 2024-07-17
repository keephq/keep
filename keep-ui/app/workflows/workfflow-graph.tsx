import { BarChart } from "@tremor/react";
import { Workflow, WorkflowExecution } from "./models";
import { useMemo } from "react";

function getColor(status: string) {
  switch (status) {
    case "success":
      return "green";
    case "failed":
    case "failure":
    case "fail":
      return "red";
    default:
      return "grey";
  }
}

const demoData = [1, 3, 2, 2, 8, 1, 3, 5, 2, 10, 1, 3, 5, 2, 10];

function getRandomStatus() {
  const statuses = ["success", "failed", "failure", "fail"];
  return statuses[Math.floor(Math.random() * statuses.length)];
}

export function getChartData(
  lastExecutions: Pick<WorkflowExecution, "execution_time" | "status" | "started">[]
) {
  if (lastExecutions?.length === 0) {
    return demoData.map((data, idx) => {
      const status = getRandomStatus();
      return {
        date: (idx + 1).toString(),
        Execution_time: data,
        color: getColor(status),
      };
    });
  }
  return lastExecutions?.map((workflowExecution) => {
    const status = workflowExecution?.status?.toLowerCase();
    return {
      date: workflowExecution?.started?.split("T")[0],
      Execution_time: workflowExecution?.execution_time,
      color: getColor(status),
    };
  });
}

export default function WorkflowGraph({ workflow }: { workflow: Workflow }) {
  type CustomTooltipTypeBar = {
    payload: any;
    active: boolean | undefined;
    label: any;
  };

  const lastExecutions = useMemo(() => {
    const reversedExecutions = workflow?.last_executions?.slice(0, 15) || [];
    return reversedExecutions.reverse();
  }, [workflow?.last_executions]);

  const chartData = getChartData(lastExecutions);

  const customTooltip = (props: CustomTooltipTypeBar) => {
    const { payload, active } = props;
    if (!active || !payload) return null;
    return (
      <div className="w-56 rounded-tremor-default border border-tremor-border bg-tremor-background p-2 text-tremor-default shadow-tremor-dropdown">
        {payload.map((category: any, idx: number) => (
          <div key={idx} className="flex flex-1 space-x-2.5">
            <div
              className="flex w-1 flex-col"
              style={{ backgroundColor: category.color, opacity: 0.2, borderTop: `2px solid ${category.color}` }}
            />
            <div className="space-y-1">
              <p className="text-tremor-content">{category.dataKey}</p>
              <p className="font-medium text-tremor-content-emphasis">
                {category.value} ms
              </p>
            </div>
          </div>
        ))}
      </div>
    );
  };

  return (
    <>
      <h3 className="text-lg font-medium text-tremor-content-strong dark:text-dark-tremor-content-strong">
        Last 7 days executions
      </h3>
      <BarChart
        className="mt-4 h-32"
        data={chartData}
        index="date"
        categories={["Execution_time"]}
        yAxisWidth={30}
        customTooltip={customTooltip}
        showGridLines={false} // Disable grid lines
        showXAxis={false}     // Disable x-axis
        showYAxis={false}     // Disable y-axis
      />
    </>
  );
}
