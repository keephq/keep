import { AreaChart } from "@tremor/react";
import Loading from "@/app/(keep)/loading";
import { AlertDto } from "@/entities/alerts/model";
import { calculateFatigue } from "utils/fatigue";

interface Props {
  minLastReceived: Date;
  maxLastReceived: Date;
  alerts: AlertDto[];
}

const getDateKey = (date: Date, timeUnit: string) => {
  if (timeUnit === "Minutes") {
    return `${date.getHours()}:${date.getMinutes()}:${date.getSeconds()}`;
  } else if (timeUnit === "Hours") {
    return `${date.getHours()}:${date.getMinutes()}`;
  } else {
    return `${date.getDate()}/${date.getMonth() + 1}/${date.getFullYear()}`;
  }
};

export default function AlertHistoryCharts({
  minLastReceived,
  maxLastReceived,
  alerts,
}: Props) {
  const categoriesByStatus: string[] = [];
  const timeDifference: number =
    maxLastReceived.getTime() - minLastReceived.getTime();
  let timeUnit = "Days";
  if (timeDifference < 3600000) {
    // Less than 1 hour (in milliseconds)
    timeUnit = "Minutes";
  } else if (timeDifference < 86400000) {
    // Less than 24 hours (in milliseconds)
    timeUnit = "Hours";
  }

  const rawChartData = [...alerts].reverse().reduce(
    (prev, curr) => {
      const date = curr.lastReceived;
      const dateKey = getDateKey(date, timeUnit);
      if (!prev[dateKey]) {
        prev[dateKey] = {
          [curr.status]: 1,
        };
      } else {
        prev[dateKey][curr.status]
          ? (prev[dateKey][curr.status] += 1)
          : (prev[dateKey][curr.status] = 1);
      }
      if (categoriesByStatus.includes(curr.status) === false) {
        categoriesByStatus.push(curr.status);
      }
      return prev;
    },
    {} as { [date: string]: any }
  );

  if (categoriesByStatus.includes("Fatigueness") === false) {
    categoriesByStatus.push("Fatigueness");
  }

  const chartData = Object.keys(rawChartData).map((key) => {
    return { ...rawChartData[key], date: key };
  });

  const newFatigueData = calculateFatigue(alerts, timeUnit);
  newFatigueData.forEach((data: any) => {
    const dataDateKey = getDateKey(data.time, timeUnit);
    const chartDataInstance = chartData.find((c) => c.date === dataDateKey);
    if (chartDataInstance) {
      chartDataInstance.Fatigueness = data.fatigueScore;
    }
  });

  return chartData === null ? (
    <Loading />
  ) : (
    <AreaChart
      className="mt-6 max-h-56"
      data={chartData}
      index="date"
      categories={categoriesByStatus}
      yAxisWidth={40}
      enableLegendSlider={true}
    />
  );
}
