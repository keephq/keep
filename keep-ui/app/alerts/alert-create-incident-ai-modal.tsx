import React, { useState, useEffect } from "react";
import Modal from "@/components/ui/Modal";
import { Callout, Button, Title } from "@tremor/react";
import { useSession } from "next-auth/react";
import { toast } from "react-toastify";
import Loading from "../loading";
import { AlertDto } from "./models";
import { IncidentDto } from "../incidents/models";
import { useConfig } from "utils/hooks/useConfig";
import { DragDropContext } from "react-beautiful-dnd";
import IncidentCard from "./alert-create-incident-ai-card";
// @ts-ignore
import incidentsData from "./incidents.json";

interface CreateIncidentWithAIModalProps {
  isOpen: boolean;
  handleClose: () => void;
  alerts: Array<AlertDto>;
}

const CreateIncidentWithAIModal = ({
  isOpen,
  handleClose,
  alerts,
}: CreateIncidentWithAIModalProps) => {
  const [isLoading, setIsLoading] = useState(false);
  const [incidentCandidates, setIncidentCandidates] = useState<IncidentDto[]>(
    []
  );
  const [changes, setChanges] = useState<Record<string, Partial<IncidentDto>>>(
    {}
  );
  const [selectedIncidents, setSelectedIncidents] = useState<string[]>([]);
  const { data: session } = useSession();
  const { data: configData } = useConfig();

  const createIncidentWithAI = async () => {
    setIsLoading(true);
    try {
      // Simulate API call delay
      await new Promise((resolve) => setTimeout(resolve, 2000));
      const newIncidentCandidates = incidentsData as unknown as IncidentDto[];
      setIncidentCandidates(newIncidentCandidates);
      setSelectedIncidents(
        newIncidentCandidates.map((incident) => incident.id)
      );
      toast.success("AI has suggested incident groupings");
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

    const newIncidentCandidates = [...incidentCandidates];
    const [movedAlert] = newIncidentCandidates[
      sourceIncidentIndex
    ].alerts.splice(result.source.index, 1);
    newIncidentCandidates[destIncidentIndex].alerts.splice(
      result.destination.index,
      0,
      movedAlert
    );

    setIncidentCandidates(newIncidentCandidates);

    // Track changes
    setChanges((prevChanges) => ({
      ...prevChanges,
      [newIncidentCandidates[sourceIncidentIndex].id]: {
        alerts: newIncidentCandidates[sourceIncidentIndex].alerts,
      },
      [newIncidentCandidates[destIncidentIndex].id]: {
        alerts: newIncidentCandidates[destIncidentIndex].alerts,
      },
    }));
  };

  const handleIncidentChange = (updatedIncident: IncidentDto) => {
    setIncidentCandidates((prevIncidents) =>
      prevIncidents.map((incident) =>
        incident.id === updatedIncident.id ? updatedIncident : incident
      )
    );

    // Track changes
    setChanges((prevChanges) => ({
      ...prevChanges,
      [updatedIncident.id]: {
        ...prevChanges[updatedIncident.id],
        ...updatedIncident,
      },
    }));
  };

  const handleCreateIncidents = async () => {
    // Here you would send the updated incidents and changes to the server
    console.log(
      "Updated Incidents:",
      incidentCandidates.filter((incident) =>
        selectedIncidents.includes(incident.id)
      )
    );
    console.log("Changes:", changes);

    // Implement the API call to create incidents here
    // For example:
    // try {
    //   const response = await fetch(`${configData?.API_URL}/incidents/create`, {
    //     method: 'POST',
    //     headers: {
    //       'Content-Type': 'application/json',
    //       Authorization: `Bearer ${session?.accessToken}`,
    //     },
    //     body: JSON.stringify({ incidents: incidentCandidates.filter(incident => selectedIncidents.includes(incident.id)), changes }),
    //   });
    //   if (response.ok) {
    //     toast.success('Incidents created successfully');
    //     handleClose();
    //   } else {
    //     toast.error('Failed to create incidents');
    //   }
    // } catch (error) {
    //   console.error('Error creating incidents:', error);
    //   toast.error('An error occurred while creating incidents');
    // }
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
                Create {selectedIncidents.length} Incident
                {selectedIncidents.length !== 1 ? "s" : ""}
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
