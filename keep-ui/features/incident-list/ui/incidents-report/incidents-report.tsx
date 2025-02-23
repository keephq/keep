import { IncidentData } from "./models";

interface IncidentsReportProps {
  incidentsReportData: IncidentData;
}

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
        <p className="font-bold">Most of the incidents reasons:</p>
        <ul className="ml-7 list-decimal">
          {Object.entries(incidentsReportData?.most_incident_reasons || {}).map(
            ([reason, incidentIds]) => (
              <li key={reason}>
                <span className="font-bold">{reason}</span>
                <span>&nbsp;-&nbsp;</span>
                <span>{incidentIds.length}times</span>
              </li>
            )
          )}
        </ul>
      </div>
    );
  }

  function renderRecurringIncidents(): JSX.Element {
    return (
      <div className="text-lg">
        <p className="font-bold">Recurring incidents:</p>
        <ul className="ml-7 list-decimal text-lg">
          {(incidentsReportData?.recurring_incidents || []).map(
            (recurringIncident) => (
              <li key={recurringIncident.incident_id}>
                <span className="font-bold">
                  {recurringIncident.incident_name}
                </span>
                <span>&nbsp;-&nbsp;</span>
                <span>{recurringIncident.occurrence_count}times</span>
              </li>
            )
          )}
        </ul>
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
    <div className="flex flex-col gap-4 mt-4">
      {renderTimeMetrics()}
      {incidentsReportData?.most_incident_reasons && renderMainReasons()}
      {incidentsReportData?.recurring_incidents && renderRecurringIncidents()}
    </div>
  );
};
