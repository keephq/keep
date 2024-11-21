import React, { useState } from "react";
import Modal from "@/components/ui/Modal";
import { Callout, Button, Title, Card } from "@tremor/react";
import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";
import { toast } from "react-toastify";
import Loading from "@/app/(keep)/loading";
import { AlertDto } from "./models";
import { IncidentDto, IncidentCandidateDto } from "@/entities/incidents/model";
import { useApiUrl } from "utils/hooks/useConfig";
import { DragDropContext } from "react-beautiful-dnd";
import IncidentCard from "./alert-create-incident-ai-card";
import { useIncidents } from "utils/hooks/useIncidents";
import { useRouter } from "next/navigation";

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
  const [changes, setChanges] = useState<
    Record<string, Record<string, IncidentChange>>
  >({});
  const [selectedIncidents, setSelectedIncidents] = useState<string[]>([]);
  const [originalSuggestions, setOriginalSuggestions] = useState<
    IncidentCandidateDto[]
  >([]);
  const [suggestionId, setSuggestionId] = useState<string>("");
  const { data: session } = useSession();
  const apiUrl = useApiUrl();
  const router = useRouter();
  const { mutate: mutateIncidents } = useIncidents(
    true,
    20,
    0,
    { id: "creation_time", desc: true },
    {}
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
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 120000); // 2 minutes timeout

      try {
        const alertsToProcess =
          alerts.length > 50 ? alerts.slice(0, 50) : alerts;

        // First attempt
        let response = await fetch(`${apiUrl}/incidents/ai/suggest`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${session?.accessToken}`,
          },
          body: JSON.stringify(
            alertsToProcess.map((alert) => alert.fingerprint)
          ),
          signal: controller.signal,
        });

        // If timeout error (which happens after 30s with NextJS), wait 10s and retry
        // This handles cases where the request goes through the NextJS server which has a 30s timeout
        // TODO: https://github.com/keephq/keep/issues/2374
        if (!response.ok && response.status === 500) {
          await new Promise((resolve) => setTimeout(resolve, 10000));
          response = await fetch(`${apiUrl}/incidents/ai/suggest`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${session?.accessToken}`,
            },
            body: JSON.stringify(
              alertsToProcess.map((alert) => alert.fingerprint)
            ),
            signal: controller.signal,
          });
        }

        if (response.ok) {
          const data: IncidentSuggestion = await response.json();
          setIncidentCandidates(data.incident_suggestion);
          setOriginalSuggestions(data.incident_suggestion);
          setSuggestionId(data.suggestion_id);

          setSelectedIncidents(
            data.incident_suggestion.map((incident) => incident.id)
          );
        } else if (response.status === 400) {
          setError(
            "Keep backend is not initialized with an AI model. See documentation on how to enable it."
          );
        } else {
          const errorData = await response.json();
          setError(
            errorData.detail || "Failed to create incident suggestions with AI"
          );
        }
      } finally {
        clearTimeout(timeoutId);
      }
    } catch (error) {
      console.error("Error creating incident with AI:", error);
      setError("An unexpected error occurred. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  const onDragEnd = (result: any) => {
    if (!result.destination) return;

    const sourceIncidentIndex = parseInt(result.source.droppableId);
    const destIncidentIndex = parseInt(result.destination.droppableId);

    const newIncidentCandidates = incidentCandidates.map((incident) => ({
      ...incident,
      alerts: [...incident.alerts],
    }));
    const [movedAlert] = newIncidentCandidates[
      sourceIncidentIndex
    ].alerts.splice(result.source.index, 1);
    newIncidentCandidates[destIncidentIndex].alerts.splice(
      result.destination.index,
      0,
      movedAlert
    );

    setIncidentCandidates(newIncidentCandidates);

    // Track changes for the alerts field
    setChanges((prevChanges) => {
      const sourceId = newIncidentCandidates[sourceIncidentIndex].id;
      const destId = newIncidentCandidates[destIncidentIndex].id;
      return {
        ...prevChanges,
        [sourceId]: {
          ...prevChanges[sourceId],
          alerts: {
            from: incidentCandidates[sourceIncidentIndex].alerts,
            to: newIncidentCandidates[sourceIncidentIndex].alerts,
          },
        },
        [destId]: {
          ...prevChanges[destId],
          alerts: {
            from: incidentCandidates[destIncidentIndex].alerts,
            to: newIncidentCandidates[destIncidentIndex].alerts,
          },
        },
      };
    });
  };

  const handleIncidentChange = (updatedIncident: IncidentCandidateDto) => {
    setIncidentCandidates((prevIncidents) =>
      prevIncidents.map((incident) =>
        incident.id === updatedIncident.id ? updatedIncident : incident
      )
    );

    // Track changes for the fields that have actually changed
    setChanges((prevChanges) => {
      const existingChanges = prevChanges[updatedIncident.id] || {};
      const newChanges: Record<string, IncidentChange> = {};

      Object.keys(updatedIncident).forEach((key) => {
        const originalIncident = incidentCandidates.find(
          (inc) => inc.id === updatedIncident.id
        );
        if (
          originalIncident &&
          updatedIncident[key as keyof IncidentCandidateDto] !==
            originalIncident[key as keyof IncidentCandidateDto]
        ) {
          newChanges[key] = {
            from: originalIncident[key as keyof IncidentCandidateDto],
            to: updatedIncident[key as keyof IncidentCandidateDto],
          };
        }
      });

      return {
        ...prevChanges,
        [updatedIncident.id]: {
          ...existingChanges,
          ...newChanges,
        },
      };
    });
  };

  const handleCreateIncidents = async () => {
    try {
      const incidentsWithFeedback = incidentCandidates.map((incident) => ({
        incident: incident,
        accepted: selectedIncidents.includes(incident.id),
        changes: changes[incident.id] || {},
        original_suggestion: originalSuggestions.find(
          (inc) => inc.id === incident.id
        ),
      }));

      const response = await fetch(
        `${apiUrl}/incidents/ai/${suggestionId}/commit`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${session?.accessToken}`,
          },
          body: JSON.stringify(incidentsWithFeedback),
        }
      );

      if (response.ok) {
        toast.success("Incidents created successfully");
        await mutateIncidents();
        handleCloseAIModal();
        router.push("/incidents");
      } else {
        const errorData = await response.json();
        setError(errorData.detail || "Failed to create incidents");
      }
    } catch (error) {
      console.error("Error creating incidents:", error);
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
          <DragDropContext onDragEnd={onDragEnd}>
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
          </DragDropContext>
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
