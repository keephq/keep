import { Button, Title, Subtitle } from "@tremor/react";
import Modal from "@/components/ui/Modal";
import { IncidentDto, Status } from "./models";
import { useApiUrl } from "utils/hooks/useConfig";
import { useSession } from "next-auth/react";
import { toast } from "react-toastify";
import { STATUS_ICONS } from "@/app/incidents/statuses";
import { useMemo, useState } from "react";
import Select, { GroupBase, StylesConfig } from "react-select";
import { clsx } from "clsx";

function IncidentRow({
  incident,
  inline = false,
}: {
  incident: IncidentDto;
  inline?: boolean;
}) {
  return (
    <div
      className={clsx(
        "flex items-center",
        !inline &&
          "px-3 py-2 border rounded-tremor-default border-tremor-border"
      )}
    >
      <div className="w-4 h-4 mr-2">{STATUS_ICONS[incident.status]}</div>
      <div className="flex-1">
        <div className="text-pretty">{incident.user_generated_name}</div>
      </div>
    </div>
  );
}

interface Props {
  incidents: IncidentDto[];
  mutate: () => void;
  handleClose: () => void;
  onSuccess?: () => void;
}

interface OptionType {
  value: string;
  label: JSX.Element;
}

// TODO: unify all selects into components/ui/Select.tsx
const customSelectStyles: StylesConfig<
  OptionType,
  false,
  GroupBase<OptionType>
> = {
  control: (provided, state) => ({
    ...provided,
    borderColor: state.isFocused ? "orange" : "rgb(229 231 235)",
    borderRadius: "0.5rem",
    "&:hover": { borderColor: "orange" },
    boxShadow: state.isFocused ? "0 0 0 1px orange" : provided.boxShadow,
  }),
  singleValue: (provided) => ({
    ...provided,
    display: "flex",
    alignItems: "center",
  }),
  menu: (provided) => ({
    ...provided,
    color: "orange",
  }),
  option: (provided, state) => ({
    ...provided,
    backgroundColor: state.isSelected ? "orange" : provided.backgroundColor,
    "&:hover": { backgroundColor: state.isSelected ? "orange" : "#f5f5f5" },
    color: state.isSelected ? "white" : "black",
  }),
};

export default function IncidentMergeModal({
  incidents,
  mutate,
  handleClose,
  onSuccess,
}: Props) {
  const { data: session } = useSession();
  const apiUrl = useApiUrl();

  const [destinationIncidentId, setDestinationIncidentId] = useState<string>(
    incidents[0].id
  );
  const destinationIncident = incidents.find(
    (incident) => incident.id === destinationIncidentId
  );
  const sourceIncidents = incidents.filter(
    (incident) => incident.id !== destinationIncidentId
  );

  const incidentOptions = useMemo(() => {
    return incidents.map((incident) => ({
      value: incident.id,
      label: <IncidentRow inline incident={incident} />,
    }));
  }, [incidents]);

  const selectValue = useMemo(() => {
    return {
      value: destinationIncidentId,
      label: <IncidentRow inline incident={destinationIncident!} />,
    };
  }, [destinationIncidentId, destinationIncident]);

  const errors = useMemo(() => {
    const errorDict: Record<string, boolean> = {};
    if (sourceIncidents.every((i) => i.status === Status.Merged)) {
      errorDict["alreadyMerged"] = true;
    }
    return errorDict;
  }, [sourceIncidents]);

  const handleMerge = async () => {
    if (!sourceIncidents.length || !destinationIncident) {
      toast.error("Please select incidents to merge.");
      return;
    }

    try {
      const response = await fetch(`${apiUrl}/incidents/merge`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session?.accessToken}`,
        },
        body: JSON.stringify({
          source_incident_ids: sourceIncidents.map((incident) => incident.id),
          destination_incident_id: destinationIncident.id,
        }),
      });

      if (response.ok) {
        toast.success("Incidents merged successfully!");
        onSuccess?.();
        mutate();
        handleClose();
      } else {
        toast.error("Failed to merge incidents.");
      }
    } catch (error) {
      toast.error("An error occurred while merging incidents.");
    }
  };

  return (
    <Modal onClose={handleClose} isOpen={true}>
      <div className="flex flex-col gap-5">
        <div>
          <Title>Merge Incidents</Title>
          <Subtitle>
            Alerts from the following incidents will be moved into the
            destination incident and the source incidents would be marked as{" "}
            <b>Merged</b>
          </Subtitle>
        </div>
        <div>
          <div className="mb-1">
            <span className="font-bold">Source Incidents</span>
            {errors.alreadyMerged && (
              <p className="text-red-500 text-sm mt-1">
                These incidents were already merged
              </p>
            )}
          </div>
          <div className="flex flex-col vertical-rounded-list">
            {sourceIncidents.map((incident) => (
              <IncidentRow key={incident.id} incident={incident} />
            ))}
          </div>
        </div>
        <div>
          <div className="mb-1">
            <span className="font-bold">Destination Incident</span>
          </div>
          <Select
            options={incidentOptions}
            value={selectValue}
            onChange={(option) => setDestinationIncidentId(option!.value)}
            placeholder="Select destination incident"
            styles={customSelectStyles}
          />
        </div>
      </div>
      <div className="flex justify-end mt-4 gap-2">
        <Button onClick={handleClose} color="orange" variant="secondary">
          Cancel
        </Button>
        <Button
          onClick={handleMerge}
          color="orange"
          disabled={Object.values(errors).length != 0}
        >
          Confirm merge
        </Button>
      </div>
    </Modal>
  );
}
