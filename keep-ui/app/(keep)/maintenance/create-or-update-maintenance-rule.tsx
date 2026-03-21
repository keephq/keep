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
  MultiSelect,
  MultiSelectItem,
} from "@tremor/react";
import { FormEvent, useEffect, useState } from "react";
import { toast } from "react-toastify";
import { MaintenanceRule } from "./model";
import { useMaintenanceRules } from "utils/hooks/useMaintenanceRules";
import { AlertsRulesBuilder } from "@/features/presets/presets-manager";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";
import { useRouter } from "next/navigation";
import { useApi } from "@/shared/lib/hooks/useApi";
import { showErrorToast } from "@/shared/ui";
import { Status } from "@/entities/alerts/model";
import { capitalize } from "@/utils/helpers";
import { useI18n } from "@/i18n/hooks/useI18n";

interface Props {
  maintenanceToEdit: MaintenanceRule | null;
  editCallback: (rule: MaintenanceRule | null) => void;
}

const DEFAULT_IGNORE_STATUSES = [
    "resolved",
    "acknowledged",
]

export default function CreateOrUpdateMaintenanceRule({
  maintenanceToEdit,
  editCallback,
}: Props) {
  const api = useApi();
  const { mutate } = useMaintenanceRules();
  const { t } = useI18n();
  const [maintenanceName, setMaintenanceName] = useState<string>("");
  const [description, setDescription] = useState<string>("");
  const [celQuery, setCelQuery] = useState<string>("");
  const [startTime, setStartTime] = useState<Date | null>(new Date());
  const [endInterval, setEndInterval] = useState<number>(5);
  const [intervalType, setIntervalType] = useState<string>("minutes");
  const [enabled, setEnabled] = useState<boolean>(true);
  const [suppress, setSuppress] = useState<boolean>(false);
  const [ignoreStatuses, setIgnoreStatuses] = useState<string[]>(DEFAULT_IGNORE_STATUSES);
  const editMode = maintenanceToEdit !== null;
  const router = useRouter();
  useEffect(() => {
    if (maintenanceToEdit) {
      setMaintenanceName(maintenanceToEdit.name);
      setDescription(maintenanceToEdit.description ?? "");
      setCelQuery(maintenanceToEdit.cel_query);
      setStartTime(new Date(maintenanceToEdit.start_time));
      setSuppress(maintenanceToEdit.suppress);
      setEnabled(maintenanceToEdit.enabled);
      setIgnoreStatuses(maintenanceToEdit.ignore_statuses);
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
    setSuppress(false);
    setEnabled(true);
    setIgnoreStatuses([]);
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
        suppress: suppress,
        enabled: enabled,
        ignore_statuses: ignoreStatuses,
      });
      clearForm();
      mutate();
      toast.success(t("maintenance.messages.createSuccess"));
    } catch (error) {
      showErrorToast(error, t("maintenance.messages.createFailed"));
    }
  };

  const updateMaintenanceRule = async (e: FormEvent) => {
    e.preventDefault();
    if (!maintenanceToEdit?.id) {
      showErrorToast(new Error("No maintenance rule selected for update"));
      return;
    }
    try {
      const response = await api.put(`/maintenance/${maintenanceToEdit.id}`, {
        name: maintenanceName,
        description: description,
        cel_query: celQuery,
        start_time: startTime,
        duration_seconds: calculateDurationInSeconds(),
        suppress: suppress,
        enabled: enabled,
        ignore_statuses: ignoreStatuses,
      });
      exitEditMode();
      mutate();
      toast.success(t("maintenance.messages.updateSuccess"));
    } catch (error) {
      showErrorToast(error, t("maintenance.messages.updateFailed"));
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
    ? t("maintenance.messages.alertsWillNotShow")
    : t("maintenance.messages.alertsWillShowSuppressed");

  return (
    <form
      className="py-2"
      onSubmit={editMode ? updateMaintenanceRule : addMaintenanceRule}
    >
      <Subtitle>{t("maintenance.metadata")}</Subtitle>
      <div className="mt-2.5">
        <Text>
          {t("maintenance.labels.name")}<span className="text-red-500 text-xs">*</span>
        </Text>
        <TextInput
          placeholder={t("maintenance.placeholders.name")}
          required={true}
          value={maintenanceName}
          onValueChange={setMaintenanceName}
        />
      </div>
      <div className="mt-2.5">
        <Text>{t("maintenance.labels.description")}</Text>
        <Textarea
          placeholder={t("maintenance.placeholders.description")}
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
        <MultiSelect value={ignoreStatuses} onValueChange={setIgnoreStatuses}>
          {Object.values(Status).map((value) => {
            return <MultiSelectItem key={value} value={value}>{capitalize(value)}</MultiSelectItem>
          })}
        </MultiSelect>
      </div>
      <div className="mt-2.5">
        <Text>
          {t("maintenance.labels.startTime")}<span className="text-red-500 text-xs">*</span>
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
          {t("maintenance.labels.endTime")}<span className="text-red-500 text-xs">*</span>
        </Text>
        <div className="flex gap-2">
          <NumberInput
            value={endInterval}
            onValueChange={setEndInterval}
            min={1}
          />
          <Select value={intervalType} onValueChange={setIntervalType}>
            <SelectItem value="minutes">{t("maintenance.timeUnits.minutes")}</SelectItem>
            <SelectItem value="hours">{t("maintenance.timeUnits.hours")}</SelectItem>
            <SelectItem value="days">{t("maintenance.timeUnits.days")}</SelectItem>
          </Select>
        </div>
        <Text className="text-xs text-red-400">
          * {t("maintenance.messages.adjustDuration")}
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
          {t("maintenance.messages.enabledTooltip")}
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
            {t("common.actions.cancel")}
          </Button>
        ) : null}
        <Button
          disabled={!submitEnabled()}
          color="orange"
          size="xs"
          type="submit"
        >
          {editMode ? t("common.actions.update") : t("common.actions.create")}
        </Button>
      </div>
    </form>
  );
}
