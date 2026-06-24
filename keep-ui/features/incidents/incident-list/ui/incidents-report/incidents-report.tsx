"use client";

import React from "react";
import { IncidentData } from "./models";
import { IncidentSeverityMetric } from "./incident-severity-metric";
import { PieChart } from "./pie-chart";
import { useTranslations } from "next-intl";

interface IncidentsReportProps {
  incidentsReportData: IncidentData;
}

export const IncidentsReport: React.FC<IncidentsReportProps> = ({
  incidentsReportData,
}) => {
  const t = useTranslations("incidents.report");

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

    if (months > 0) result.push(`${months} ${months > 1 ? t("months") : t("month")}`);
    if (weeks > 0) result.push(`${weeks} ${weeks > 1 ? t("weeks") : t("week")}`);
    if (days > 0) result.push(`${days} ${days > 1 ? t("days") : t("day")}`);
    if (hours > 0) result.push(`${hours} ${hours > 1 ? t("hours") : t("hour")}`);
    if (minutes > 0) result.push(`${minutes} ${minutes > 1 ? t("minutes") : t("minute")}`);
    if (seconds > 0) result.push(`${seconds} ${seconds > 1 ? t("seconds") : t("second")}`);

    return result.join(" ");
  }

  function formatIncidentsCount(count: number): string {
    return count > 1 ? `${count} ${t("incidents")}` : `${count} ${t("incident")}`;
  }

  function renderTimeMetric(
    metricName: string,
    metricValueInSeconds: number | undefined
  ): React.JSX.Element {
    return (
      <p className="incidents-time-metric font-medium text-lg">
        <strong>{metricName}:&nbsp;</strong>
        <span>
          {metricValueInSeconds && convertSeconds(metricValueInSeconds)}
        </span>
      </p>
    );
  }

  function renderMainReasons(): React.JSX.Element {
    return (
      <div className="break-inside-avoid incidents-main-reasons text-lg">
        <p className="font-bold mb-2">{t("mostReasons")}</p>
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

  function renderAffectedServices(): React.JSX.Element {
    return (
      <div className="break-inside-avoid text-lg">
        <p className="font-bold mb-2">{t("affectedServices")}</p>
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

  function renderRecurringIncidents(): React.JSX.Element {
    return (
      <div className="text-lg break-inside-avoid">
        <p className="font-bold mb-2">{t("recurringIncidents")}</p>
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

  function renderTimeMetrics(): React.JSX.Element {
    return (
      <div className="break-inside-avoid">
        <p className="font-bold text-lg">{t("incidentMetrics")}</p>
        <div className="pl-4">
          {renderTimeMetric(
            t("mttd"),
            incidentsReportData?.mean_time_to_detect_seconds
          )}
          {renderTimeMetric(
            t("mttr"),
            incidentsReportData?.mean_time_to_resolve_seconds
          )}
          {incidentsReportData?.incident_durations &&
            renderTimeMetric(
              t("shortestDuration"),
              incidentsReportData?.incident_durations?.shortest_duration_seconds
            )}
          {incidentsReportData?.incident_durations &&
            renderTimeMetric(
              t("longestDuration"),
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
