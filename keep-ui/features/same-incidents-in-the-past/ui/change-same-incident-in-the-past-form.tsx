import { Button, Divider, Title } from "@tremor/react";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { useIncidents, usePollIncidents } from "@/utils/hooks/useIncidents";
import Loading from "@/app/(keep)/loading";
import type { IncidentDto } from "@/entities/incidents/model";
import { useIncidentActions } from "@/entities/incidents/model";
import { getIncidentName } from "@/entities/incidents/lib/utils";
import { Select } from "@/shared/ui";

interface ChangeSameIncidentInThePastFormProps {
  incident: IncidentDto;
  handleClose: () => void;
  linkedIncident: IncidentDto | null;
}

export function ChangeSameIncidentInThePastForm({
  incident,
  handleClose,
  linkedIncident,
}: ChangeSameIncidentInThePastFormProps) {
  const { data: incidents, isLoading } = useIncidents(true, null, 100);

  const [selectedIncident, setSelectedIncident] = useState<string | undefined>(
    linkedIncident?.id
  );
  const { updateIncident, mutateIncidentsList } = useIncidentActions();
  const router = useRouter();
  usePollIncidents(mutateIncidentsList);

  const associateIncidentHandler = async (
    selectedIncidentId: string | null
  ) => {
    try {
      await updateIncident(
        incident.id,
        {
          user_generated_name: incident.user_generated_name,
          user_summary: incident.user_summary,
          assignee: incident.assignee,
          same_incident_in_the_past_id: selectedIncidentId,
        },
        false
      );
      handleClose();
    } catch (error) {
      console.error(error);
    }
  };

  const handleLinkIncident = (e: FormEvent) => {
    e.preventDefault();
    if (!selectedIncident) {
      return;
    }
    associateIncidentHandler(selectedIncident);
  };

  const handleUnlinkIncident = (e: FormEvent) => {
    e.preventDefault();
    associateIncidentHandler(null);
  };

  const renderSelectIncidentForm = () => {
    if (!incidents || !incidents.items.length) {
      return (
        <div className="flex flex-col items-center justify-center gap-y-8 h-full">
          <div className="text-center space-y-3">
            <Title className="text-2xl">No Incidents Yet</Title>
          </div>

          <div className="flex items-center justify-between w-full gap-6">
            <Button
              className="flex-1"
              color="orange"
              onClick={() => router.push("/incidents")}
            >
              Incidents page
            </Button>
          </div>
        </div>
      );
    }

    const selectedIncidentInstance = incidents.items.find(
      (incident) => incident.id === selectedIncident
    );

    return (
      <form className="h-full justify-center">
        <Select
          className="my-2.5"
          placeholder="Select incident"
          value={
            selectedIncidentInstance
              ? {
                  value: selectedIncidentInstance.id,
                  label: getIncidentName(selectedIncidentInstance),
                }
              : null
          }
          onChange={(selectedOption) =>
            setSelectedIncident(selectedOption?.value)
          }
          options={incidents.items
            ?.filter(
              (incident_iteration_on) =>
                incident_iteration_on.id !== incident.id
            )
            .map((incident_iteration_on) => ({
              value: incident_iteration_on.id,
              label: getIncidentName(incident_iteration_on),
            }))}
        />
        <Divider />
        <div className="flex items-center justify-end gap-2">
          {selectedIncident && (
            <Button
              color="red"
              onClick={handleUnlinkIncident}
              disabled={selectedIncident === null}
            >
              Unlink
            </Button>
          )}
          <Button
            color="orange"
            onClick={handleLinkIncident}
            disabled={selectedIncident === null}
          >
            Link and help AI
          </Button>
        </div>
      </form>
    );
  };

  return (
    <div className="relative">
      {isLoading ? <Loading /> : renderSelectIncidentForm()}
    </div>
  );
}
