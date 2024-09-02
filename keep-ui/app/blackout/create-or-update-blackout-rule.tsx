import {
  TextInput,
  Textarea,
  Divider,
  Subtitle,
  Text,
  Button,
  Switch,
  NumberInput,
  Select,
  SelectItem,
} from "@tremor/react";
import { useSession } from "next-auth/react";
import { FormEvent, useEffect, useState } from "react";
import { toast } from "react-toastify";
import { getApiURL } from "utils/apiUrl";
import { BlackoutRule } from "./model";
import { useBlackouts } from "utils/hooks/useBlackoutRules";
import { AlertsRulesBuilder } from "app/alerts/alerts-rules-builder";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";

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
  const [startTime, setStartTime] = useState<Date | null>(new Date());
  const [endInterval, setEndInterval] = useState<number>(5);
  const [intervalType, setIntervalType] = useState<string>("minutes");
  const [enabled, setEnabled] = useState<boolean>(true);
  const editMode = blackoutToEdit !== null;

  useEffect(() => {
    if (blackoutToEdit) {
      setBlackoutName(blackoutToEdit.name);
      setDescription(blackoutToEdit.description ?? "");
      setCelQuery(blackoutToEdit.cel_query);
      setStartTime(new Date(blackoutToEdit.start_time));
      setEnabled(blackoutToEdit.enabled);
      if (blackoutToEdit.duration_seconds) {
        setEndInterval(blackoutToEdit.duration_seconds / 60);
      }
    }
  }, [blackoutToEdit]);

  const clearForm = () => {
    setBlackoutName("");
    setDescription("");
    setCelQuery("");
    setStartTime(new Date());
    setEndInterval(5);
    setEnabled(true);
  };

  const calculateDurationInSeconds = () => {
    let durationInSeconds = 0;
    switch (intervalType) {
      case "seconds":
        durationInSeconds = endInterval;
        break;
      case "minutes":
        durationInSeconds = endInterval * 60;
        break;
      case "hours":
        durationInSeconds = endInterval * 60 * 60;
        break;
      case "days":
        durationInSeconds = endInterval * 60 * 60 * 24;
        break;
      default:
        console.error("Invalid interval type");
    }
    return durationInSeconds;
  };

  const addBlackout = async (e: FormEvent) => {
    e.preventDefault();
    const apiUrl = getApiURL();
    const response = await fetch(`${apiUrl}/blackout`, {
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
        duration_seconds: calculateDurationInSeconds(),
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
    const response = await fetch(`${apiUrl}/blackout/${blackoutToEdit?.id}`, {
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
        duration_seconds: calculateDurationInSeconds(),
        enabled: enabled,
      }),
    });
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

  const date = new Date();
  const currentMins = date.getMinutes();
  const currentHour = date.getHours();

  return (
    <form className="py-2" onSubmit={editMode ? updateBlackout : addBlackout}>
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
        <AlertsRulesBuilder
          defaultQuery={celQuery}
          updateOutputCEL={setCelQuery}
          showSave={false}
          showSqlImport={false}
        />
      </div>
      <div className="mt-2.5">
        <Text>
          Start At<span className="text-red-500 text-xs">*</span>
        </Text>
        <DatePicker
          onChange={(date) => setStartTime(date)}
          showTimeSelect
          selected={startTime}
          timeFormat="p"
          timeIntervals={15}
          minDate={new Date()}
          timeCaption="Time"
          dateFormat="MMMM d, yyyy h:mm:ss aa"
          inline
        />
      </div>
      <div className="mt-2.5">
        <Text>
          End After<span className="text-red-500 text-xs">*</span>
        </Text>
        <div className="flex gap-2">
          <NumberInput
            defaultValue={5}
            value={endInterval}
            onValueChange={setEndInterval}
            min={1}
          />
          <Select value={intervalType} onValueChange={setIntervalType}>
            <SelectItem value="minutes">Minutes</SelectItem>
            <SelectItem value="hours">Hours</SelectItem>
            <SelectItem value="days">Days</SelectItem>
          </Select>
        </div>
        <Text className="text-xs text-red-400">
          * Please adjust when editing existing blackout rule, as this is
          calculated upon submit.
        </Text>
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
