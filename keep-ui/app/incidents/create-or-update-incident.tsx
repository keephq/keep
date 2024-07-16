"use client";

import {
  TextInput,
  Textarea,
  Divider,
  Subtitle,
  Text,
  Button,
} from "@tremor/react";
import { useSession } from "next-auth/react";
import { FormEvent, useEffect, useState } from "react";
import { toast } from "react-toastify";
import { getApiURL } from "utils/apiUrl";
import { IncidentDto } from "./model";
import { useIncidents } from "utils/hooks/useIncidents";

interface Props {
  incidentToEdit: IncidentDto | null;
  editCallback: (rule: IncidentDto | null) => void;
}

export default function CreateOrUpdateIncident({
  incidentToEdit,
  editCallback,
}: Props) {
  const { data: session } = useSession();
  const { mutate } = useIncidents();
  const [incidentName, setIncidentName] = useState<string>("");
  const [incidentDescription, setIncidentDescription] = useState<string>("");
  const [incidentAssignee, setIncidentAssignee] = useState<string>("");
  const editMode = incidentToEdit !== null;


  useEffect(() => {
    if (incidentToEdit) {
      setIncidentName(incidentToEdit.name);
      setIncidentDescription(incidentToEdit.description ?? "");
      setIncidentAssignee(incidentToEdit.assignee ?? "");
    }
  }, [incidentToEdit]);

  const clearForm = () => {
    setIncidentName("");
    setIncidentDescription("");
    setIncidentAssignee("");
  };

  const addIncident = async (e: FormEvent) => {
    e.preventDefault();
    const apiUrl = getApiURL();
    const response = await fetch(`${apiUrl}/incidents`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${session?.accessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        name: incidentName,
        description: incidentDescription,
        assignee: incidentAssignee,
      }),
    });
    if (response.ok) {
      exitEditMode();
      await mutate();
      toast.success("Incident created successfully");
    } else {
      toast.error(
        "Failed to create incident, please contact us if this issue persists."
      );
    }
  };

  // This is the function that will be called on submitting the form in the editMode, it sends a PUT request to the backend.
  const updateIncident = async (e: FormEvent) => {
    e.preventDefault();
    const apiUrl = getApiURL();
    const response = await fetch(
      `${apiUrl}/incidents/${incidentToEdit?.incident_fingerprint}`,
      {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${session?.accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: incidentName,
          description: incidentDescription,
          assignee: incidentAssignee,
        }),
      }
    );
    if (response.ok) {
      exitEditMode();
      await mutate();
      toast.success("Incident updated successfully");
    } else {
      toast.error(
        "Failed to update incident, please contact us if this issue persists."
      );
    }
  };

  // If the Incident is successfully updated or the user cancels the update we exit the editMode and set the editRule in the incident.tsx to null.
  const exitEditMode = () => {
    editCallback(null);
    clearForm();
  };

  const submitEnabled = (): boolean => {
    return (
      !!incidentName &&
      !!incidentDescription
    );
  };

  return (
    <form
      className="py-2"
      onSubmit={editMode ? updateIncident : addIncident}
    >
      <Subtitle>Incident Metadata</Subtitle>
      <div className="mt-2.5">
        <Text>
          Name<span className="text-red-500 text-xs">*</span>
        </Text>
        <TextInput
          placeholder="Incident Name"
          required={true}
          value={incidentName}
          onValueChange={setIncidentName}
        />
      </div>
      <div className="mt-2.5">
        <Text>Description<span className="text-red-500 text-xs">*</span></Text>
        <Textarea
          placeholder="What happened?"
          required={true}
          value={incidentDescription}
          onValueChange={setIncidentDescription}
        />
      </div>

      <div className="mt-2.5">
        <Text>Assignee</Text>
        <TextInput
          placeholder="Who is responsible"
          value={incidentAssignee}
          onValueChange={setIncidentAssignee}
        />
      </div>

      <Divider />


      <div className={"space-x-1 flex flex-row justify-end items-center"}>
        {/*If we are in the editMode we need an extra cancel button option for the user*/}
        {editMode ? (
          <Button
            color="orange"
            size="xs"
            variant="secondary"
            onClick={exitEditMode}
          >
            Cancel
          </Button>
        ) : (
          <></>
        )}
        <Button
          disabled={!submitEnabled()}
          color="orange"
          size="xs"
          type="submit"
        >
          {editMode ? "Update" : "Create"}
        </Button>
      </div>
    </form>
  );
}
