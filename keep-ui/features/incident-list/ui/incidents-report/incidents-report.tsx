import { IncidentData } from "./models";
import { IncidentSeverityMetric } from "./incident-severity-metric";
import { PieChart } from "./pie-chart";

interface IncidentsReportProps {
  incidentsReportData: IncidentData;
}

export const IncidentsReport: React.FC<IncidentsReportProps> = ({
  incidentsReportData,
}) => {
  function convertSeconds(secondsValue: number): string {
    const result = [];

    const secondsInMinute = 60;
    const secondsInHour = 60 * secondsInMinute;
    const secondsInDay = 24 * secondsInHour;
    const secondsInWeek = 7 * secondsInDay;
    const secondsInMonth = 30 * secondsInDay; // Approximation

    const months = Math.floor(secondsValue / secondsInMonth);
    secondsValue %= secondsInMonth;

    const weeks = Math.floor(secondsValue / secondsInWeek);
    secondsValue %= secondsInWeek;

    const days = Math.floor(secondsValue / secondsInDay);
    secondsValue %= secondsInDay;

    const hours = Math.floor(secondsValue / secondsInHour);
    secondsValue %= secondsInHour;

    const minutes = Math.floor(secondsValue / secondsInMinute);
    const seconds = secondsValue % secondsInMinute;

    if (months > 0) result.push(`${months} month${months > 1 ? "s" : ""}`);
    if (weeks > 0) result.push(`${weeks} week${weeks > 1 ? "s" : ""}`);
    if (days > 0) result.push(`${days} day${days > 1 ? "s" : ""}`);
    if (hours > 0) result.push(`${hours} hour${hours > 1 ? "s" : ""}`);
    if (minutes > 0) result.push(`${minutes} minute${minutes > 1 ? "s" : ""}`);
    if (seconds > 0) result.push(`${seconds} second${seconds > 1 ? "s" : ""}`);

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
      <p className="incidents-time-metric font-medium text-lg">
        <strong>{metricName}:&nbsp;</strong>
        <span>
          {metricValueInSeconds && convertSeconds(metricValueInSeconds)}
        </span>
      </p>
    );
  }

  function renderMainReasons(): JSX.Element {
    return (
      <div className="break-inside-avoid incidents-main-reasons text-lg">
        <p className="font-bold mb-2">Most of the incidents reasons:</p>
        <PieChart
          formatCount={formatIncidentsCount}
          data={Object.entries(
            incidentsReportData?.most_frequent_reasons || {}
          ).map(([reason, incidentIds]) => ({
            name: reason,
            value: incidentIds.length,
          }))}
        />
      </div>
    );
  }

  function renderAffectedServices(): JSX.Element {
    return (
      <div className="break-inside-avoid text-lg">
        <p className="font-bold mb-2">Affected services:</p>
        <PieChart
          formatCount={formatIncidentsCount}
          data={Object.entries(
            incidentsReportData?.services_affected_metrics || {}
          ).map(([reason, count]) => ({
            name: reason,
            value: count,
          }))}
        />
      </div>
    );
  }

  function renderRecurringIncidents(): JSX.Element {
    return (
      <div className="text-lg break-inside-avoid">
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
      <div className="break-inside-avoid">
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
          {incidentsReportData?.incident_durations &&
            renderTimeMetric(
              "Shortest Incident Duration",
              incidentsReportData?.incident_durations?.shortest_duration_seconds
            )}
          {incidentsReportData?.incident_durations &&
            renderTimeMetric(
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
      {incidentsReportData?.severity_metrics && (
        <IncidentSeverityMetric
          severityMetrics={incidentsReportData.severity_metrics}
        />
      )}
      {incidentsReportData?.services_affected_metrics &&
        renderAffectedServices()}
      {incidentsReportData?.most_frequent_reasons && renderMainReasons()}
      {incidentsReportData?.recurring_incidents && renderRecurringIncidents()}
    </div>
  );
};
