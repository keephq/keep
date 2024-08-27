"use client";

import { InformationCircleIcon } from "@heroicons/react/24/outline";
import {
  TextInput,
  Textarea,
  Divider,
  Subtitle,
  Text,
  Button,
  Icon,
  Badge,
} from "@tremor/react";
import { useSession } from "next-auth/react";
import { FormEvent, useEffect, useState } from "react";
import { toast } from "react-toastify";
import { getApiURL } from "utils/apiUrl";
import { BlackoutRule } from "./model";
import { useBlackouts } from "utils/hooks/useBlackoutRules";

interface Props {
  blackoutToEdit: BlackoutRule | null;
  editCallback: (rule: BlackoutRule | null) => void;
}

export default function CreateOrUpdateBlackoutRule({
  blackoutToEdit,
  editCallback,
}: Props) {
  const { data: session } = useSession();
  const { mutate } = useBlackouts();
  const [blackoutName, setBlackoutName] = useState<string>("");
  const [description, setDescription] = useState<string>("");
  const [celQuery, setCelQuery] = useState<string>("");
  const [startTime, setStartTime] = useState<string>("");
  const [endTime, setEndTime] = useState<string>("");
  const [enabled, setEnabled] = useState<boolean>(true);
  const editMode = blackoutToEdit !== null;

  useEffect(() => {
    if (blackoutToEdit) {
      setBlackoutName(blackoutToEdit.name);
      setDescription(blackoutToEdit.description ?? "");
      setCelQuery(blackoutToEdit.cel_query);
      setStartTime(blackoutToEdit.start_time);
      setEndTime(blackoutToEdit.end_time ?? "");
      setEnabled(blackoutToEdit.enabled);
    }
  }, [blackoutToEdit]);

  const clearForm = () => {
    setBlackoutName("");
    setDescription("");
    setCelQuery("");
    setStartTime("");
    setEndTime("");
    setEnabled(true);
  };

  const addBlackout = async (e: FormEvent) => {
    e.preventDefault();
    const apiUrl = getApiURL();
    const response = await fetch(`${apiUrl}/blackouts`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${session?.accessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        name: blackoutName,
        description: description,
        cel_query: celQuery,
        start_time: startTime,
        end_time: endTime,
        enabled: enabled,
      }),
    });
    if (response.ok) {
      clearForm();
      mutate();
      toast.success("Blackout rule created successfully");
    } else {
      toast.error(
        "Failed to create blackout rule, please contact us if this issue persists."
      );
    }
  };

  const updateBlackout = async (e: FormEvent) => {
    e.preventDefault();
    const apiUrl = getApiURL();
    const response = await fetch(
      `${apiUrl}/blackouts/${blackoutToEdit?.id}`,
      {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${session?.accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: blackoutName,
          description: description,
          cel_query: celQuery,
          start_time: startTime,
          end_time: endTime,
          enabled: enabled,
        }),
      }
    );
    if (response.ok) {
      exitEditMode();
      mutate();
      toast.success("Blackout rule updated successfully");
    } else {
      toast.error(
        "Failed to update blackout rule, please contact us if this issue persists."
      );
    }
  };

  const exitEditMode = () => {
    editCallback(null);
    clearForm();
  };

  const submitEnabled = (): boolean => {
    return !!blackoutName && !!celQuery && !!startTime;
  };

  return (
    <form
      className="py-2"
      onSubmit={editMode ? updateBlackout : addBlackout}
    >
      <Subtitle>Blackout Metadata</Subtitle>
      <div className="mt-2.5">
        <Text>
          Name<span className="text-red-500 text-xs">*</span>
        </Text>
        <TextInput
          placeholder="Blackout Name"
          required={true}
          value={blackoutName}
          onValueChange={setBlackoutName}
        />
      </div>
      <div className="mt-2.5">
        <Text>Description</Text>
        <Textarea
          placeholder="Blackout Description"
          value={description}
          onValueChange={setDescription}
        />
      </div>
      <div className="mt-2.5">
        <Text>
          CEL Query<span className="text-red-500 text-xs">*</span>
          <a
            href="https://docs.keephq.dev/overview/presets"
            target="_blank"
          >
            <Icon
              icon={InformationCircleIcon}
              size="xs"
              color="gray"
              tooltip="CEL Query to match alerts during blackout"
            />
          </a>
        </Text>
        <TextInput
          placeholder="CEL Query"
          required={true}
          value={celQuery}
          onValueChange={setCelQuery}
        />
      </div>
      <div className="mt-2.5">
        <Text>
          Start Time<span className="text-red-500 text-xs">*</span>
        </Text>
        <TextInput
          placeholder="YYYY-MM-DDTHH:mm:ss"
          required={true}
          value={startTime}
          onValueChange={setStartTime}
        />
      </div>
      <div className="mt-2.5">
        <Text>End Time</Text>
        <TextInput
          placeholder="YYYY-MM-DDTHH:mm:ss"
          value={endTime}
          onValueChange={setEndTime}
        />
      </div>
      <div className="mt-2.5">
        <Text>Enabled</Text>
        <Switch checked={enabled} onChange={setEnabled} />
      </div>
      <Divider />
      <div className={"space-x-1 flex flex-row justify-end items-center"}>
        {editMode ? (
          <Button
            color="orange"
            size="xs"
            variant="secondary"
            onClick={exitEditMode}
          >
            Cancel
          </Button>
        ) : null}
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
