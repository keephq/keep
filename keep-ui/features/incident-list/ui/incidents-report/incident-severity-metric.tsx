import React, { useCallback, useEffect, useMemo, useRef } from "react";
import { Button } from "@/components/ui";
import Modal from "@/components/ui/Modal";
import { KeepLoader } from "@/shared/ui";
import { useReactToPrint } from "react-to-print";
import { useReportData } from "./use-report-data";
import { IncidentData } from "./models";
import { IncidentsReport } from "./incidents-report";
import { PrinterIcon } from "@heroicons/react/24/outline";
import { SeverityMetrics } from "./models";
import { DonutChart } from "@tremor/react";

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
                <span>{formatIncidentsCount(chartValue.value)}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
