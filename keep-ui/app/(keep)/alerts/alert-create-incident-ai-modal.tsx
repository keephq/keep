import React, { useState } from "react";
import Modal from "@/components/ui/Modal";
import { Callout, Button, Title, Card } from "@tremor/react";
import { toast } from "react-toastify";
import Loading from "@/app/(keep)/loading";
import { AlertDto } from "@/entities/alerts/model";
import { IncidentCandidateDto } from "@/entities/incidents/model";
import {
  DndContext,
  DragEndEvent,
  DragOverEvent,
  DragStartEvent,
  closestCenter,
  DragOverlay,
  MeasuringStrategy,
} from "@dnd-kit/core";
import { restrictToVerticalAxis } from "@dnd-kit/modifiers";
import { createPortal } from "react-dom";
import IncidentCard from "./alert-create-incident-ai-card";
import { useIncidents } from "utils/hooks/useIncidents";
import { useRouter } from "next/navigation";
import { useApi } from "@/shared/lib/hooks/useApi";
import { KeepApiError } from "@/shared/api";
import { FormattedContent } from "@/shared/ui/FormattedContent/FormattedContent";

interface CreateIncidentWithAIModalProps {
  isOpen: boolean;
  handleClose: () => void;
  alerts: Array<AlertDto>;
}

interface IncidentChange {
  from: any;
  to: any;
}

interface IncidentSuggestion {
  incident_suggestion: IncidentCandidateDto[];
  suggestion_id: string;
}

function deepCopy<T>(obj: T): T {
  return JSON.parse(JSON.stringify(obj));
}

const CreateIncidentWithAIModal = ({
  isOpen,
  handleClose,
  alerts,
}: CreateIncidentWithAIModalProps) => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [incidentCandidates, setIncidentCandidates] = useState<
    IncidentCandidateDto[]
  >([]);
  const [selectedIncidents, setSelectedIncidents] = useState<string[]>([]);
  const [originalSuggestions, setOriginalSuggestions] = useState<
    IncidentCandidateDto[]
  >([]);
  const [suggestionId, setSuggestionId] = useState<string>("");
  const api = useApi();
  const router = useRouter();
  const { mutate: mutateIncidents } = useIncidents(
    false,
    null,
    20,
    0,
    { id: "creation_time", desc: true },
    "",
    {}
  );
  const [activeAlert, setActiveAlert] = useState<AlertDto | null>(null);
  const [activeIncidentIndex, setActiveIncidentIndex] = useState<number | null>(
    null
  );

  const handleCloseAIModal = () => {
    setError(null);
    setSelectedIncidents([]);
    setOriginalSuggestions([]);
    setIncidentCandidates([]);
    handleClose();
  };

  const createIncidentWithAI = async () => {
    setIsLoading(true);
    setError(null);

    function handleSuccess(data: IncidentSuggestion) {
      setIncidentCandidates(data.incident_suggestion);
      // Deep copy the incident suggestions to avoid mutating the original suggestions, we later compare the original suggestions with the current state
      setOriginalSuggestions(deepCopy(data.incident_suggestion));
      setSuggestionId(data.suggestion_id);

      setSelectedIncidents(
        data.incident_suggestion.map((incident) => incident.id)
      );
    }

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 120000); // 2 minutes timeout

      try {
        const alertsToProcess =
          alerts.length > 50 ? alerts.slice(0, 50) : alerts;

        let data: IncidentSuggestion;

        const fetchIncidentSuggestions = async (
          alertsToProcess: AlertDto[],
          controller: AbortController
        ) => {
          return await api.post(
            "/incidents/ai/suggest",
            alertsToProcess.map((alert) => alert.fingerprint),
            { signal: controller.signal }
          );
        };

        // First attempt
        try {
          data = await fetchIncidentSuggestions(alertsToProcess, controller);
          handleSuccess(data);
        } catch (error) {
          // If timeout error (which happens after 30s with NextJS), wait 10s and retry
          // This handles cases where the request goes through the NextJS server which has a 30s timeout
          // TODO: https://github.com/keephq/keep/issues/2374
          if (error instanceof KeepApiError && error.statusCode === 500) {
            await new Promise((resolve) => setTimeout(resolve, 10000));
            data = await fetchIncidentSuggestions(alertsToProcess, controller);
            handleSuccess(data);
          }
        }
      } finally {
        clearTimeout(timeoutId);
      }
    } catch (error) {
      if (error instanceof KeepApiError) {
        if (error.statusCode === 400) {
          setError(
            "Keep backend is not initialized with an AI model. See documentation on how to enable it."
          );
        } else {
          setError(
            error.message || "Failed to create incident suggestions with AI"
          );
        }
      } else {
        setError("An unexpected error occurred. Please try again.");
      }
      console.error("Error creating incident with AI:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const onDragStart = (event: DragStartEvent) => {
    const { active } = event;
    if (!active?.data?.current) return;

    const sourceIncidentIndex = parseInt(active.data.current.incidentIndex);
    const alertIndex = active.data.current.alertIndex;

    if (isNaN(sourceIncidentIndex) || !incidentCandidates[sourceIncidentIndex])
      return;

    setActiveIncidentIndex(sourceIncidentIndex);
    setActiveAlert(incidentCandidates[sourceIncidentIndex].alerts[alertIndex]);
  };

  const onDragOver = (event: DragOverEvent) => {
    const { active, over } = event;
    if (!over || !active?.data?.current || !over?.data?.current) return;

    const sourceIncidentIndex = parseInt(active.data.current.incidentIndex);
    const destIncidentIndex = parseInt(over.data.current.incidentIndex);

    if (
      isNaN(sourceIncidentIndex) ||
      isNaN(destIncidentIndex) ||
      sourceIncidentIndex === destIncidentIndex
    )
      return;

    setIncidentCandidates((prev) => {
      if (!prev[sourceIncidentIndex] || !prev[destIncidentIndex]) return prev;

      const newIncidents = [...prev];
      const sourceIncident = { ...newIncidents[sourceIncidentIndex] };
      const destIncident = { ...newIncidents[destIncidentIndex] };

      const alertIndex = active.data.current?.alertIndex;
      if (typeof alertIndex !== "number") return prev;

      sourceIncident.alerts = [...sourceIncident.alerts];
      const [movedAlert] = sourceIncident.alerts.splice(alertIndex, 1);
      const overIndex =
        over.data.current?.alertIndex ?? destIncident.alerts.length;
      destIncident.alerts = [...destIncident.alerts];
      destIncident.alerts.splice(overIndex, 0, movedAlert);

      newIncidents[sourceIncidentIndex] = sourceIncident;
      newIncidents[destIncidentIndex] = destIncident;

      return newIncidents;
    });
  };

  const onDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || !active?.data?.current || !over?.data?.current) {
      setActiveAlert(null);
      setActiveIncidentIndex(null);
      return;
    }

    const sourceIncidentIndex = parseInt(active.data.current.incidentIndex);
    const destIncidentIndex = parseInt(over.data.current.incidentIndex);

    if (
      isNaN(sourceIncidentIndex) ||
      isNaN(destIncidentIndex) ||
      !incidentCandidates[sourceIncidentIndex] ||
      !incidentCandidates[destIncidentIndex]
    ) {
      setActiveAlert(null);
      setActiveIncidentIndex(null);
      return;
    }

    setActiveAlert(null);
    setActiveIncidentIndex(null);
  };

  const handleIncidentChange = (updatedIncident: IncidentCandidateDto) => {
    setIncidentCandidates((prevIncidents) =>
      prevIncidents.map((incident) =>
        incident.id === updatedIncident.id ? updatedIncident : incident
      )
    );
  };

  const handleCreateIncidents = async () => {
    try {
      const incidentsWithFeedback = incidentCandidates.map((incident) => {
        const originalIncident = originalSuggestions.find(
          (inc) => inc.id === incident.id
        );

        // Calculate changes by comparing current state with original state
        const changes: Record<string, IncidentChange> = {};

        if (originalIncident) {
          // Compare each field and track changes
          Object.keys(incident).forEach((key) => {
            const currentValue = incident[key as keyof IncidentCandidateDto];
            const originalValue =
              originalIncident[key as keyof IncidentCandidateDto];

            if (
              JSON.stringify(currentValue) !== JSON.stringify(originalValue)
            ) {
              changes[key] = {
                from: originalValue,
                to: currentValue,
              };
            }
          });
        }

        return {
          incident: incident,
          accepted: selectedIncidents.includes(incident.id),
          changes: changes,
          original_suggestion: originalIncident,
        };
      });

      const response = await api.post(
        `/incidents/ai/${suggestionId}/commit`,
        incidentsWithFeedback
      );

      toast.success("Incidents created successfully");
      await mutateIncidents();
      handleCloseAIModal();
      router.push("/incidents");
    } catch (error) {
      console.error("Error creating incidents:", error);
      if (error instanceof KeepApiError) {
        setError(error.message || "Failed to create incidents");
      } else {
        setError("An unexpected error occurred. Please try again.");
      }
    }
  };

  const toggleIncidentSelection = (incidentId: string) => {
    setSelectedIncidents((prev) =>
      prev.includes(incidentId)
        ? prev.filter((id) => id !== incidentId)
        : [...prev, incidentId]
    );
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleCloseAIModal}
      beta={true}
      title="Create Incidents with AI"
      className="max-w-[600px] w-full lg:max-w-[1200px]"
    >
      <div className="relative bg-white p-6 rounded-lg">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center">
            <Loading loadingText="This is taking a bit longer then usual, please wait..." />
          </div>
        ) : incidentCandidates.length > 0 ? (
          <DndContext
            onDragStart={onDragStart}
            onDragOver={onDragOver}
            onDragEnd={onDragEnd}
            collisionDetection={closestCenter}
            measuring={{
              droppable: {
                strategy: MeasuringStrategy.Always,
              },
            }}
            modifiers={[restrictToVerticalAxis]}
          >
            <div className="space-y-6">
              <Callout
                title="Help the AI out by adjusting the incident groupings"
                color="orange"
              >
                - Drag and drop alerts between incidents to adjust the incidents
                and improve the AI&apos;s algorithm.
                <br />- Click on an incident to edit its name and summary.
              </Callout>
              {incidentCandidates.map((incident, index) => (
                <div key={incident.id} className="flex items-center space-x-4">
                  <div className="flex items-center h-full">
                    <input
                      type="checkbox"
                      id={`incident-${incident.id}`}
                      checked={selectedIncidents.includes(incident.id)}
                      onChange={() => toggleIncidentSelection(incident.id)}
                      className="w-5 h-5 text-orange-500 border-orange-500 rounded focus:ring-orange-500"
                    />
                  </div>
                  <IncidentCard
                    incident={incident}
                    index={index}
                    onIncidentChange={handleIncidentChange}
                  />
                </div>
              ))}
              <Button
                className="w-full"
                color="orange"
                onClick={handleCreateIncidents}
              >
                Create Incidents
              </Button>
            </div>
            {createPortal(
              <DragOverlay dropAnimation={null}>
                {activeAlert && activeIncidentIndex !== null && (
                  <div className="bg-white shadow-lg rounded p-2 border border-gray-200 min-w-[800px] flex items-center gap-4">
                    <div className="w-1/6 break-words font-medium">
                      {activeAlert.name || "Unnamed Alert"}
                    </div>
                    <div className="w-2/3 break-words whitespace-normal text-gray-600">
                      <FormattedContent
                        content={activeAlert.description || "No description"}
                        format={activeAlert.description_format}
                      />
                    </div>
                    <div className="w-1/12 break-words">
                      <span className="bg-orange-100 text-orange-800 px-2 py-1 rounded text-sm">
                        {activeAlert.severity || "N/A"}
                      </span>
                    </div>
                    <div className="w-1/12 break-words text-gray-600">
                      {activeAlert.status || "N/A"}
                    </div>
                  </div>
                )}
              </DragOverlay>,
              document.body
            )}
          </DndContext>
        ) : (
          <Card className="flex flex-col items-center h-[400px] p-8">
            <Title className="text-2xl">Create New Incident with AI</Title>
            <div className="flex-1" />
            <div className="w-full flex flex-col items-center">
              {alerts.length > 50 ? (
                <Callout
                  title="Alert Limit"
                  color="orange"
                  className="w-full mb-4"
                >
                  You have selected {alerts.length} alerts. Keep currently
                  supports only 50 alerts at a time. Only the first 50 alerts
                  will be processed.
                </Callout>
              ) : (
                <Callout
                  title="AI Analysis"
                  color="purple"
                  className="w-full mb-4"
                >
                  AI will analyze {alerts.length} alert
                  {alerts.length > 1 ? "s" : ""} and suggest incident groupings.
                </Callout>
              )}
              {error && (
                <Callout title="Error" color="red" className="w-full mb-4">
                  {error}
                </Callout>
              )}
            </div>
            <div className="flex-1" />
            <Button
              className="w-full"
              color="orange"
              onClick={createIncidentWithAI}
            >
              Generate incident suggestions with AI
            </Button>
          </Card>
        )}
      </div>
    </Modal>
  );
};

export default CreateIncidentWithAIModal;
