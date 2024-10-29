"use client";

import {
  TextInput,
  Divider,
  Subtitle,
  Text,
  Button,
  Select,
  SelectItem,
} from "@tremor/react";
import { FormEvent, useEffect, useState } from "react";
import { IncidentDto } from "./models";
import { useUsers } from "utils/hooks/useUsers";
const ReactQuill =
  typeof window === "object" ? require("react-quill") : () => false;
import "react-quill/dist/quill.snow.css";
import "./react-quill-override.css";
import { useIncidentActions } from "@/entities/incidents/model/useIncidentActions";

interface Props {
  incidentToEdit: IncidentDto | null;
  createCallback?: (id: string) => void;
  exitCallback?: () => void;
}

export default function CreateOrUpdateIncident({
  incidentToEdit,
  createCallback,
  exitCallback,
}: Props) {
  const [incidentName, setIncidentName] = useState<string>("");
  const [incidentUserSummary, setIncidentUserSummary] = useState<string>("");
  const [incidentAssignee, setIncidentAssignee] = useState<string>("");
  const { data: users = [] } = useUsers();
  const { addIncident, updateIncident } = useIncidentActions();

  const editMode = incidentToEdit !== null;

  // Display cancel btn if editing or we need to cancel for another reason (eg. going one step back in the modal etc.)
  const cancellable = editMode || exitCallback;

  useEffect(() => {
    if (incidentToEdit) {
      setIncidentName(
        incidentToEdit.user_generated_name ??
          incidentToEdit.ai_generated_name ??
          ""
      );
      setIncidentUserSummary(
        incidentToEdit.user_summary ?? incidentToEdit.generated_summary ?? ""
      );
      setIncidentAssignee(incidentToEdit.assignee ?? "");
    }
  }, [incidentToEdit]);

  const clearForm = () => {
    setIncidentName("");
    setIncidentUserSummary("");
    setIncidentAssignee("");
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
          same_incident_in_the_past_id:
            incidentToEdit!.same_incident_in_the_past_id,
        },
        false
      );
      exitEditMode();
    } else {
      const newIncident = await addIncident({
        user_generated_name: incidentName,
        user_summary: incidentUserSummary,
        assignee: incidentAssignee,
      });
      createCallback?.(newIncident.id);
      exitEditMode();
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
          required={false}
          onValueChange={setIncidentUserSummary}
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
