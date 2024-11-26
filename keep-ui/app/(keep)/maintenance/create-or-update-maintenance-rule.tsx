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
import { FormEvent, useEffect, useState } from "react";
import { toast } from "react-toastify";
import { MaintenanceRule } from "./model";
import { useMaintenanceRules } from "utils/hooks/useMaintenanceRules";
import { AlertsRulesBuilder } from "@/app/(keep)/alerts/alerts-rules-builder";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";
import { useRouter } from "next/navigation";
import { useApi } from "@/shared/lib/hooks/useApi";
import { KeepApiError } from "@/shared/lib/api/KeepApiError";

interface Props {
  maintenanceToEdit: MaintenanceRule | null;
  editCallback: (rule: MaintenanceRule | null) => void;
}

export default function CreateOrUpdateMaintenanceRule({
  maintenanceToEdit,
  editCallback,
}: Props) {
  const api = useApi();
  const { mutate } = useMaintenanceRules();
  const [maintenanceName, setMaintenanceName] = useState<string>("");
  const [description, setDescription] = useState<string>("");
  const [celQuery, setCelQuery] = useState<string>("");
  const [startTime, setStartTime] = useState<Date | null>(new Date());
  const [endInterval, setEndInterval] = useState<number>(5);
  const [intervalType, setIntervalType] = useState<string>("minutes");
  const [enabled, setEnabled] = useState<boolean>(true);
  const [suppress, setSuppress] = useState<boolean>(false);
  const editMode = maintenanceToEdit !== null;
  const router = useRouter();
  useEffect(() => {
    if (maintenanceToEdit) {
      setMaintenanceName(maintenanceToEdit.name);
      setDescription(maintenanceToEdit.description ?? "");
      setCelQuery(maintenanceToEdit.cel_query);
      setStartTime(new Date(maintenanceToEdit.start_time));
      setEnabled(maintenanceToEdit.enabled);
      if (maintenanceToEdit.duration_seconds) {
        setEndInterval(maintenanceToEdit.duration_seconds / 60);
      }
    }
  }, [maintenanceToEdit]);

  const clearForm = () => {
    setMaintenanceName("");
    setDescription("");
    setCelQuery("");
    setStartTime(new Date());
    setEndInterval(5);
    setEnabled(true);
    router.replace("/maintenance");
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

  const addMaintenanceRule = async (e: FormEvent) => {
    e.preventDefault();
    try {
      const response = await api.post("/maintenance", {
        name: maintenanceName,
        description: description,
        cel_query: celQuery,
        start_time: startTime,
        duration_seconds: calculateDurationInSeconds(),
        enabled: enabled,
      });
      clearForm();
      mutate();
      toast.success("Maintenance rule created successfully");
    } catch (error) {
      if (error instanceof KeepApiError) {
        toast.error(error.message || "Failed to create maintenance rule");
      } else {
        toast.error(
          "Failed to create maintenance rule, please contact us if this issue persists."
        );
      }
    }
  };

  const updateMaintenanceRule = async (e: FormEvent) => {
    e.preventDefault();
    if (!maintenanceToEdit?.id) {
      toast.error("No maintenance rule selected for update");
      return;
    }
    try {
      const response = await api.put(`/maintenance/${maintenanceToEdit.id}`, {
        name: maintenanceName,
        description: description,
        cel_query: celQuery,
        start_time: startTime,
        duration_seconds: calculateDurationInSeconds(),
        enabled: enabled,
      });
      exitEditMode();
      mutate();
      toast.success("Maintenance rule updated successfully");
    } catch (error) {
      if (error instanceof KeepApiError) {
        toast.error(error.message || "Failed to update maintenance rule");
      } else {
        toast.error(
          "Failed to update maintenance rule, please contact us if this issue persists."
        );
      }
    }
  };

  const exitEditMode = () => {
    editCallback(null);
    clearForm();
  };

  const submitEnabled = (): boolean => {
    return !!maintenanceName && !!celQuery && !!startTime;
  };

  const ignoreText = !suppress
    ? "Alerts will not show in feed"
    : "Alerts will show in suppressed status";

  return (
    <form
      className="py-2"
      onSubmit={editMode ? updateMaintenanceRule : addMaintenanceRule}
    >
      <Subtitle>Maintenance Rule Metadata</Subtitle>
      <div className="mt-2.5">
        <Text>
          Name<span className="text-red-500 text-xs">*</span>
        </Text>
        <TextInput
          placeholder="Maintenance Name"
          required={true}
          value={maintenanceName}
          onValueChange={setMaintenanceName}
        />
      </div>
      <div className="mt-2.5">
        <Text>Description</Text>
        <Textarea
          placeholder="Maintenance Description"
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
          * Please adjust when editing existing maintenance rule, as this is
          calculated upon submit.
        </Text>
      </div>
      <div className="flex items-center space-x-3 mt-2.5 w-[300px] justify-between">
        <label
          htmlFor="ignoreSwitch"
          className="text-tremor-default text-tremor-content dark:text-dark-tremor-content"
        >
          {ignoreText}
        </label>
        <Switch id="ignoreSwitch" checked={suppress} onChange={setSuppress} />
      </div>
      <div className="flex items-center space-x-3 w-[300px] justify-between mt-2.5">
        <label
          htmlFor="enabledSwitch"
          className="text-tremor-default text-tremor-content dark:text-dark-tremor-content"
        >
          Whether this rule is enabled or not
        </label>
        <Switch id="enabledSwitch" checked={enabled} onChange={setEnabled} />
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
