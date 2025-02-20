import React, { useEffect } from "react";
import { Button, Link } from "@/components/ui";
import Modal from "@/components/ui/Modal";
import useSWR from "swr";
import { useApi } from "@/shared/lib/hooks/useApi";
import { KeepLoader } from "@/shared/ui";

interface IncidentMetrics {
  total_incidents: number;
  resolved_incidents: number;
  deleted_incidents: number;
  unresolved_incidents: number;
}

interface IncidentDurations {
  shortest_duration_seconds: number;
  shortest_duration_incident_id: string;
  longest_duration_seconds: number;
  longest_duration_incident_id: string;
}

interface SeverityMetrics {
  critical: string;
  high: string;
}

interface IncidentData {
  incident_metrics: IncidentMetrics;
  top_services_affected: string[];
  common_incident_names: string[];
  severity_metrics: SeverityMetrics;
  incident_durations: IncidentDurations;
  mean_time_to_detect_seconds: number;
  mean_time_to_resolve_seconds: number;
  most_occuring_incidents: string[];
  most_incident_reasons: Record<string, string[]>;
}

interface GenerateReportModalProps {
  incidentIds: string[];
  onClose: () => void;
}

const useReportData = (incidentIds: string[]) => {
  const api = useApi();
  const ids_query = incidentIds.map((id) => `'${id}'`).join(",");
  const cel_query = `id in [${ids_query}]`;
  const requestUrl = `/incidents/report?cel=${cel_query}`;

  const swrValue = useSWR<IncidentData>(
    () => (api.isReady() ? requestUrl : null),
    (url) => api.get(url),
    { revalidateOnFocus: false }
  );
  return swrValue;
};

const GenerateReportModal: React.FC<GenerateReportModalProps> = ({
  incidentIds,
  onClose,
}) => {
  const { data, isLoading } = useReportData(incidentIds);

  useEffect(() => {
    console.log("Ihor", data);
  }, [data]);

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
      result.push(`${days} days`);
    }

    if (hours > 0) {
      result.push(`${hours} hours`);
    }

    if (minutes % 60 > 0) {
      result.push(`${minutes % 60} minutes`);
    }

    if (secondsValue % 60 > 0) {
      result.push(`${secondsValue % 60} seconds`);
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
      <div>
        <p className="font-bold text-lg">Most of the incidents reasons:</p>
        <ul className="ml-7 list-decimal">
          {Object.entries(data?.most_incident_reasons || {}).map(
            ([reason, incidentIds]) => (
              <li key={reason}>
                <h3 className="font-medium text-lg">{reason}</h3>
              </li>
            )
          )}
        </ul>
      </div>
    );
  }

  function renderReport(): JSX.Element {
    return (
      <div className="text-2xl">
        {renderTimeMetric(
          "Average Mean Time To Detect (MTTD)",
          data?.mean_time_to_detect_seconds
        )}
        {renderTimeMetric(
          "Average Mean Time To Resolve (MTTR)",
          data?.mean_time_to_resolve_seconds
        )}
        {renderTimeMetric(
          "Shortest Incident Duration",
          data?.incident_durations?.shortest_duration_seconds
        )}
        {renderTimeMetric(
          "Longest Incident Duration",
          data?.incident_durations?.longest_duration_seconds
        )}
        {data?.most_incident_reasons && renderMainReasons()}
      </div>
    );
  }

  return (
    <Modal
      title="Generate Report"
      className="min-w-[80vw] h-[80vh]"
      isOpen={true}
      onClose={onClose}
    >
      <div>
        {isLoading && <KeepLoader />}
        {!isLoading && renderReport()}
      </div>
    </Modal>
  );
};

export default GenerateReportModal;
