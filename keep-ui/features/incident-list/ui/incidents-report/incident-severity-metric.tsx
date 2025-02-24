import React, { useMemo } from "react";
import { SeverityMetrics } from "./models";
import { DonutChart } from "@tremor/react";
import {
  getSeverityBgClassName,
  UISeverity,
} from "@/shared/ui/utils/severity-utils";

interface IncidentSeverityMetricProps {
  severityMetrics: SeverityMetrics;
}

export const IncidentSeverityMetric: React.FC<IncidentSeverityMetricProps> = ({
  severityMetrics: severityMetric,
}) => {
  const sortedByValue = useMemo(() => {
    Object.entries(severityMetric);
    return Object.entries(severityMetric)
      .map(([name, value]) => ({ name, value: value.length }))
      .sort((a, b) => b.value - a.value);
  }, [severityMetric]);

  const severityBgColorDictionary = useMemo(
    () =>
      Object.fromEntries(
        Object.values(UISeverity).map((severity) => [
          severity,
          getSeverityBgClassName(severity),
        ])
      ),
    []
  );

  const severityColorsSorted = useMemo(
    () =>
      sortedByValue.map((chartValue) =>
        getSeverityBgClassName(chartValue.name as UISeverity).replace("bg-", "")
      ),
    [sortedByValue]
  );

  function formatIncidentsCount(count: number): string {
    return count > 1 ? `${count} incidents` : `${count} incident`;
  }

  return (
    <div className="break-inside-avoid text-lg">
      <p className="font-bold mb-2">Incidents severity:</p>
      <div className="flex items-center gap-10">
        <DonutChart
          className="w-48 h-48"
          data={sortedByValue}
          colors={severityColorsSorted}
          variant="pie"
          onValueChange={(v) => console.log(v)}
        />
        <div className="flex-col">
          {sortedByValue.map((chartValue, index) => (
            <div key={chartValue.name} className="flex gap-2">
              <div
                className={`min-w-5 h-3 mt-2 ${severityBgColorDictionary[chartValue.name]}`}
              ></div>
              <div>
                <span className="font-bold">{chartValue.name}</span> -{" "}
                <span>{formatIncidentsCount(chartValue.value)}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
