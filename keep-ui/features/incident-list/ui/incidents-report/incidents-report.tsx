import { useMemo } from "react";
import { IncidentData } from "./models";
import { DonutChart } from "@tremor/react";

interface IncidentsReportProps {
  incidentsReportData: IncidentData;
}

interface PieChartProps {
  data: { name: string; value: number }[];
  formatCount?: (value: number) => string;
}

export const PieChart: React.FC<PieChartProps> = ({
  data,
  formatCount: counterFormatter,
}) => {
  const sortedByValue = useMemo(() => {
    return [...data].sort((a, b) => b.value - a.value);
  }, [data]);

  const colors = useMemo(
    () => ["red", "blue", "green", "orange", "yellow", "purple"],
    []
  ); // Tremor color names

  // Tremor color name to HEX mapping (based on Tailwind)
  const tremorColorMap = useMemo(
    () => ({
      blue: "bg-blue-700",
      red: "bg-red-500",
      green: "bg-green-500",
      orange: "bg-orange-500",
      yellow: "bg-yellow-500",
      purple: "bg-purple-500",
      teal: "bg-teal-500",
      cyan: "bg-cyan-500",
      rose: "bg-rose-500",
      lime: "bg-lime-500",
    }),
    []
  );

  function getCategoryColor(index: number): string {
    const categoryColor = colors[index];
    return tremorColorMap[categoryColor as keyof typeof tremorColorMap];
  }

  return (
    <div className="flex items-center gap-10">
      <DonutChart
        className="w-48 h-48"
        data={sortedByValue}
        colors={colors}
        variant="pie"
        onValueChange={(v) => console.log(v)}
      />
      <div className="flex-col">
        {sortedByValue.map((chartValue, index) => (
          <div key={chartValue.name} className="flex gap-2">
            <div
              className={`min-w-5 h-3 mt-2 ${getCategoryColor(index)}`}
            ></div>
            <div>
              <span className="font-bold">{chartValue.name}</span> -{" "}
              {counterFormatter && (
                <span>{counterFormatter(chartValue.value)}</span>
              )}
              {!counterFormatter && <span>{chartValue.value}</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export const IncidentsReport: React.FC<IncidentsReportProps> = ({
  incidentsReportData,
}) => {
  function convertSeconds(secondsValue: number): string {
    const minutes = Math.floor(secondsValue / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);
    const weeks = Math.floor(days / 7);
    const months = Math.floor(weeks / 4);

    const result = [];

    if (months > 0) {
      result.push(`${months} months`);
    }

    if (weeks > 0) {
      result.push(`${weeks} weeks`);
    }

    if (days > 0) {
      const daysStr = days == 1 ? "day" : "days";
      result.push(`${days} ${daysStr}`);
    }

    if (hours > 0) {
      const hoursStr = hours == 1 ? "hour" : "hours";
      result.push(`${hours} ${hoursStr}`);
    }

    if (minutes % 60 > 0) {
      const minutesStr = minutes % 60 == 1 ? "minute" : "minutes";
      result.push(`${minutes % 60} ${minutesStr}`);
    }

    if (secondsValue % 60 > 0) {
      const secondsStr = secondsValue % 60 == 1 ? "second" : "seconds";
      result.push(`${secondsValue % 60} ${secondsStr}`);
    }

    return result.join(" ");
  }

  function formatIncidentsCount(count: number): string {
    return count > 1 ? `${count} incidents` : `${count} incident`;
  }

  function renderTimeMetric(
    metricName: string,
    metricValueInSeconds: number | undefined
  ): JSX.Element {
    return (
      <p className="font-medium text-lg">
        <strong>{metricName}:&nbsp;</strong>
        <span>
          {metricValueInSeconds && convertSeconds(metricValueInSeconds)}
        </span>
      </p>
    );
  }

  function renderMainReasons(): JSX.Element {
    return (
      <div className="text-lg">
        <p className="font-bold mb-2">Most of the incidents reasons:</p>
        <PieChart
          formatCount={formatIncidentsCount}
          data={Object.entries(
            incidentsReportData?.most_incident_reasons || {}
          ).map(([reason, incidentIds]) => ({
            name: reason,
            value: incidentIds.length,
          }))}
        />
      </div>
    );
  }

  function renderRecurringIncidents(): JSX.Element {
    return (
      <div className="text-lg">
        <p className="font-bold mb-2">Recurring incidents:</p>
        <PieChart
          formatCount={formatIncidentsCount}
          data={incidentsReportData?.recurring_incidents.map(
            (recurringIncident) => ({
              name: recurringIncident.incident_name as string,
              value: recurringIncident.occurrence_count as number,
            })
          )}
        />
      </div>
    );
  }

  function renderTimeMetrics(): JSX.Element {
    return (
      <div>
        <p className="font-bold text-lg">Incident Metrics:</p>
        <div className="pl-4">
          {renderTimeMetric(
            "Mean Time To Detect (MTTD)",
            incidentsReportData?.mean_time_to_detect_seconds
          )}
          {renderTimeMetric(
            "Mean Time To Resolve (MTTR)",
            incidentsReportData?.mean_time_to_resolve_seconds
          )}
          {renderTimeMetric(
            "Shortest Incident Duration",
            incidentsReportData?.incident_durations?.shortest_duration_seconds
          )}
          {renderTimeMetric(
            "Longest Incident Duration",
            incidentsReportData?.incident_durations?.longest_duration_seconds
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 mt-4 px-6">
      {renderTimeMetrics()}
      {incidentsReportData?.most_incident_reasons && renderMainReasons()}
      {incidentsReportData?.recurring_incidents && renderRecurringIncidents()}
    </div>
  );
};
