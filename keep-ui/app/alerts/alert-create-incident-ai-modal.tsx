import React, { useState, useEffect, use } from "react";
import Modal from "@/components/ui/Modal";
import { Callout, Button, Title } from "@tremor/react";
import { useSession } from "next-auth/react";
import { toast } from "react-toastify";
import Loading from "../loading";
import { AlertDto } from "./models";
import { IncidentDto, IncidentCandidatDto } from "../incidents/models";
import { useApiUrl, useConfig } from "utils/hooks/useConfig";
import { DragDropContext } from "react-beautiful-dnd";
import IncidentCard from "./alert-create-incident-ai-card";
import { useIncidents } from "utils/hooks/useIncidents";

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
  incident_suggestion: IncidentCandidatDto[];
  suggestion_id: string;
}

const CreateIncidentWithAIModal = ({
  isOpen,
  handleClose,
  alerts,
}: CreateIncidentWithAIModalProps) => {
  const [isLoading, setIsLoading] = useState(false);
  const [incidentCandidates, setIncidentCandidates] = useState<
    IncidentCandidatDto[]
  >([]);
  const [changes, setChanges] = useState<
    Record<string, Record<string, IncidentChange>>
  >({});
  const [selectedIncidents, setSelectedIncidents] = useState<string[]>([]);
  const [originalSuggestions, setOriginalSuggestions] = useState<
    IncidentCandidatDto[]
  >([]);
  const [suggestionId, setSuggestionId] = useState<string>("");
  const { data: session } = useSession();
  const { data: configData } = useConfig();
  const apiUrl = useApiUrl();
  const { mutate: mutateIncidents } = useIncidents(
    true,
    20,
    0,
    { id: "creation_time", desc: true },
    {}
  );

  const createIncidentWithAI = async () => {
    setIsLoading(true);
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 120000); // 2 minutes timeout

      try {
        const response = await fetch(`${apiUrl}/incidents/ai/suggest`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${session?.accessToken}`,
          },
          body: JSON.stringify(alerts.map((alert) => alert.fingerprint)),
          signal: controller.signal,
        });
        if (response.ok) {
          const data: IncidentSuggestion = await response.json();
          setIncidentCandidates(data.incident_suggestion);
          setOriginalSuggestions(data.incident_suggestion);
          setSuggestionId(data.suggestion_id);

          setSelectedIncidents(
            data.incident_suggestion.map((incident) => incident.id)
          );
          toast.success("AI has suggested incident groupings");
        } else {
          toast.error("Failed to create incident suggestions with AI");
        }
      } finally {
        clearTimeout(timeoutId);
      }
    } catch (error) {
      console.error("Error creating incident with AI:", error);
      toast.error("An unexpected error occurred. Please try again.");
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

  const handleIncidentChange = (updatedIncident: IncidentCandidatDto) => {
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
          updatedIncident[key as keyof IncidentCandidatDto] !==
            originalIncident[key as keyof IncidentCandidatDto]
        ) {
          newChanges[key] = {
            from: originalIncident[key as keyof IncidentCandidatDto],
            to: updatedIncident[key as keyof IncidentCandidatDto],
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
        `${configData?.API_URL}/incidents/ai/${suggestionId}/commit`,
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
        handleClose();
      } else {
        const errorData = await response.json();
        toast.error(`Failed to create incidents: ${errorData.detail}`);
      }
    } catch (error) {
      console.error("Error creating incidents:", error);
      toast.error("An unexpected error occurred while creating incidents");
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
      onClose={handleClose}
      beta={true}
      title="Create Incidents with AI"
      className="w-[90%] max-w-6xl"
    >
      <div className="relative bg-white p-6 rounded-lg">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center">
            <Loading />
            <Title className="mt-4">
              Creating incident suggestions with AI...
            </Title>
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
          <div className="flex flex-col items-center justify-center gap-y-8 h-full">
            <div className="text-center space-y-3">
              <Title className="text-2xl">Create New Incident with AI</Title>
              <p>
                AI will analyze {alerts.length} alert
                {alerts.length > 1 ? "s" : ""} and suggest incident groupings.
              </p>
            </div>
            <Button
              className="w-full"
              color="green"
              onClick={createIncidentWithAI}
            >
              Generate incident suggestions with AI
            </Button>
          </div>
        )}
      </div>
    </Modal>
  );
};

export default CreateIncidentWithAIModal;
