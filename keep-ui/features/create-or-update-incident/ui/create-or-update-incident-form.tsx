"use client";

import {
  TextInput,
  Divider,
  Subtitle,
  Text,
  Button,
  Select,
  SelectItem,
  Switch,
} from "@tremor/react";
import { FormEvent, useEffect, useState } from "react";
import { useUsers } from "@/entities/users/model/useUsers";
import { useIncidentActions } from "@/entities/incidents/model";
import type { IncidentDto } from "@/entities/incidents/model";
import { getIncidentName } from "@/entities/incidents/lib/utils";
import "react-quill-new/dist/quill.snow.css";
import "./react-quill-override.css";
import dynamic from "next/dynamic";

const ReactQuill = dynamic(() => import("react-quill-new"), { ssr: false });

interface Props {
  incidentToEdit: IncidentDto | null;
  createCallback?: (id: string) => void;
  exitCallback?: () => void;
}

export function CreateOrUpdateIncidentForm({
  incidentToEdit,
  createCallback,
  exitCallback,
}: Props) {
  const [incidentName, setIncidentName] = useState<string>("");
  const [incidentUserSummary, setIncidentUserSummary] = useState<string>("");
  const [incidentAssignee, setIncidentAssignee] = useState<string>("");
  const [resolveOnAlertsResolved, setResolveOnAlertsResolved] =
    useState<string>("all");
  const { data: users = [] } = useUsers();
  const { addIncident, updateIncident } = useIncidentActions();

  const editMode = incidentToEdit !== null;

  // Display cancel btn if editing or we need to cancel for another reason (eg. going one step back in the modal etc.)
  const cancellable = editMode || exitCallback;

  useEffect(() => {
    if (incidentToEdit) {
      setIncidentName(getIncidentName(incidentToEdit));
      setIncidentUserSummary(
        incidentToEdit.user_summary ?? incidentToEdit.generated_summary ?? ""
      );
      setIncidentAssignee(incidentToEdit.assignee ?? "");
      setResolveOnAlertsResolved(incidentToEdit.resolve_on ?? "all");
    }
  }, [incidentToEdit]);

  const clearForm = () => {
    setIncidentName("");
    setIncidentUserSummary("");
    setIncidentAssignee("");
    setResolveOnAlertsResolved("all");
  };

  // If the Incident is successfully updated or the user cancels the update we exit the editMode and set the editRule in the incident.tsx to null.
  const exitEditMode = () => {
    exitCallback?.();
    clearForm();
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (editMode) {
      await updateIncident(
        incidentToEdit!.id,
        {
          user_generated_name: incidentName,
          user_summary: incidentUserSummary,
          assignee: incidentAssignee,
          resolve_on: resolveOnAlertsResolved,
          same_incident_in_the_past_id:
            incidentToEdit!.same_incident_in_the_past_id,
        },
        false
      );
      exitEditMode();
    } else {
      try {
        const newIncident = await addIncident({
          user_generated_name: incidentName,
          user_summary: incidentUserSummary,
          assignee: incidentAssignee,
          resolve_on: resolveOnAlertsResolved,
        });
        createCallback?.(newIncident.id);
        exitEditMode();
      } catch (error) {
        console.error(error);
      }
    }
  };

  const submitEnabled = (): boolean => {
    return !!incidentName;
  };

  const formats = [
    "header",
    "bold",
    "italic",
    "underline",
    "list",
    "bullet",
    "link",
    "align",
    "blockquote",
    "code-block",
    "color",
  ];

  const modules = {
    toolbar: [
      [{ header: "1" }, { header: "2" }],
      [{ list: "ordered" }, { list: "bullet" }],
      ["bold", "italic", "underline"],
      ["link"],
      [{ align: [] }],
      ["blockquote", "code-block"], // Add quote and code block options to the toolbar
      [{ color: [] }], // Add color option to the toolbar
    ],
  };

  return (
    <form className="py-2" onSubmit={handleSubmit}>
      <Subtitle>Incident Metadata</Subtitle>
      <div className="mt-2.5">
        <Text className="mb-2">
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
        <Text className="mb-2">Summary</Text>
        <ReactQuill
          value={incidentUserSummary}
          onChange={(value: string) => setIncidentUserSummary(value)}
          theme="snow" // Use the Snow theme
          modules={modules}
          formats={formats} // Add formats
          placeholder="What happened?"
          className="border border-tremor-border rounded-tremor-default shadow-tremor-input"
        />
      </div>

      <div className="mt-2.5">
        <Text className="mb-2">Assignee</Text>
        {users.length > 0 ? (
          <Select
            placeholder="Who is responsible"
            value={incidentAssignee}
            onValueChange={setIncidentAssignee}
          >
            {users.map((user) => (
              <SelectItem key={user.email} value={user.email}>
                {user.name || user.email}
              </SelectItem>
            ))}
          </Select>
        ) : (
          <TextInput
            placeholder="Who is responsible"
            value={incidentAssignee}
            onValueChange={setIncidentAssignee}
          />
        )}
      </div>

      <div className="mt-2.5">
        <div className="flex items-center space-x-2">
          <Switch
            id="resolve-on-alerts"
            name="resolve-on-alerts"
            color="orange"
            checked={resolveOnAlertsResolved === "all_resolved"}
            onChange={() =>
              setResolveOnAlertsResolved(
                resolveOnAlertsResolved === "all_resolved"
                  ? "never"
                  : "all_resolved"
              )
            }
          />
          <Text>Resolve when all alerts are resolved</Text>
        </div>
      </div>

      <Divider />

      <div className="mt-auto pt-6 space-x-1 flex flex-row justify-end items-center">
        {cancellable && (
          <Button
            color="orange"
            size="xs"
            variant="secondary"
            onClick={exitEditMode}
          >
            Cancel
          </Button>
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
