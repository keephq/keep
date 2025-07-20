import { Trashcan } from "@/components/icons";
import { Preset } from "@/entities/presets/model";
import {
  Button,
  Icon,
  Select,
  SelectItem,
  Subtitle,
  TextInput,
  Switch,
} from "@tremor/react";
import { useEffect, useMemo, useState } from "react";
import {
  Controller,
  get,
  useForm,
  useWatch,
  useFieldArray,
} from "react-hook-form";
import { LayoutItem, Threshold, PresetPanelType } from "../../types";
import ColumnsSelection from "./columns-selection";

interface PresetForm {
  selectedPreset: string;
  countOfLastAlerts: string;
  thresholds: Threshold[];
  presetPanelType: PresetPanelType;
  showFiringOnly: boolean;
}

export interface PresetWidgetFormProps {
  editingItem?: any;
  presets: Preset[];
  onChange: (formState: any, isValid: boolean) => void;
}

export const PresetWidgetForm: React.FC<PresetWidgetFormProps> = ({
  editingItem,
  presets,
  onChange,
}: PresetWidgetFormProps) => {
  const {
    control,
    formState: { errors, isValid },
    register,
  } = useForm<PresetForm>({
    defaultValues: {
      selectedPreset: editingItem?.preset?.id,
      countOfLastAlerts: editingItem
        ? editingItem.preset.countOfLastAlerts || 0
        : 5,
      thresholds: editingItem?.thresholds || [
        { value: 0, color: "#22c55e" }, // Green
        { value: 20, color: "#ef4444" }, // Red
      ],
      presetPanelType: editingItem?.presetPanelType || PresetPanelType.ALERT_TABLE,
      showFiringOnly: editingItem?.showFiringOnly ?? false,
    },
  });
  const [presetColumns, setPresetColumns] = useState<string[] | undefined>(
    editingItem ? editingItem.presetColumns : undefined
  );

  const { fields, append, remove, move, replace } = useFieldArray({
    control,
    name: "thresholds",
  });

  const formValues = useWatch({ control });

  const normalizedFormValues = useMemo(() => {
    return {
      countOfLastAlerts: parseInt(formValues.countOfLastAlerts || "0"),
      selectedPreset: presets.find((p) => p.id === formValues.selectedPreset),
      presetColumns,
      thresholds: formValues.thresholds?.map((t) => ({
        ...t,
        value: parseInt(t.value?.toString() as string, 10) || 0,
      })),
      presetPanelType: formValues.presetPanelType || PresetPanelType.ALERT_TABLE,
      showFiringOnly: formValues.showFiringOnly ?? false,
    };
  }, [formValues, presetColumns]);

  function getLayoutValues(): LayoutItem {
    if (editingItem) {
      return {} as LayoutItem;
    }

    const isAlertTable = normalizedFormValues.presetPanelType === PresetPanelType.ALERT_TABLE;
    const itemHeight = isAlertTable && normalizedFormValues.countOfLastAlerts > 0 ? 6 : 4;
    const itemWidth = isAlertTable && normalizedFormValues.countOfLastAlerts > 0 ? 4 : 3;

    return {
      w: itemWidth,
      h: itemHeight,
      minW: 4,
      minH: 4,
      static: false,
    } as LayoutItem;
  }

  useEffect(() => {
    onChange(
      {
        ...getLayoutValues(),
        preset: {
          ...normalizedFormValues.selectedPreset,
          countOfLastAlerts: normalizedFormValues.countOfLastAlerts,
        },
        presetColumns: normalizedFormValues.presetColumns,
        thresholds: normalizedFormValues.thresholds,
        presetPanelType: normalizedFormValues.presetPanelType,
        showFiringOnly: normalizedFormValues.showFiringOnly,
      },
      isValid
    );
  }, [normalizedFormValues, isValid]);

  const handleThresholdBlur = () => {
    const reorderedThreesholds = formValues?.thresholds
      ?.map((t) => ({
        ...t,
        value: parseInt(t.value?.toString() as string, 10) || 0,
      }))
      .sort((a, b) => a.value - b.value);
    if (!reorderedThreesholds) {
      return;
    }
    replace(reorderedThreesholds as any);
  };

  const handleAddThreshold = () => {
    const maxThreshold = Math.max(
      ...(formValues.thresholds?.map((t) => t.value) as any),
      0
    );
    append({ value: maxThreshold + 10, color: "#000000" });
  };

  return (
    <>
      <div className="mb-4 mt-2">
        <Subtitle>Preset</Subtitle>
        <Controller
          name="selectedPreset"
          control={control}
          rules={{
            required: {
              value: true,
              message: "Preset selection is required",
            },
          }}
          render={({ field }) => (
            <Select
              {...field}
              placeholder="Select a preset"
              error={!!get(errors, "selectedPreset.message")}
              errorMessage={get(errors, "selectedPreset.message")}
            >
              {presets.map((preset) => (
                <SelectItem key={preset.id} value={preset.id}>
                  {preset.name}
                </SelectItem>
              ))}
            </Select>
          )}
        />
      </div>
      <div className="mb-4 mt-2">
        <Subtitle>Panel Type</Subtitle>
        <Controller
          name="presetPanelType"
          control={control}
          rules={{
            required: {
              value: true,
              message: "Panel type selection is required",
            },
          }}
          render={({ field }) => (
            <Select
              {...field}
              placeholder="Select a panel type"
              error={!!get(errors, "presetPanelType.message")}
              errorMessage={get(errors, "presetPanelType.message")}
            >
              <SelectItem value={PresetPanelType.ALERT_TABLE}>
                Alert Table
              </SelectItem>
              <SelectItem value={PresetPanelType.ALERT_COUNT_PANEL}>
                Alert Count Panel
              </SelectItem>
            </Select>
          )}
        />
      </div>
      {formValues.presetPanelType === PresetPanelType.ALERT_COUNT_PANEL && (
        <div className="mb-4 mt-2">
          <div className="flex items-center justify-between">
            <Subtitle>Show Firing Alerts Only</Subtitle>
            <Controller
              name="showFiringOnly"
              control={control}
              render={({ field }) => (
                <Switch
                  checked={field.value}
                  onChange={field.onChange}
                />
              )}
            />
          </div>
        </div>
      )}
      {formValues.presetPanelType === PresetPanelType.ALERT_TABLE && (
        <>
          <div className="mb-4 mt-2">
            <Subtitle>Last alerts count to display</Subtitle>
            <Controller
              name="countOfLastAlerts"
              control={control}
              rules={{
                required: {
                  value: true,
                  message: "Preset selection is required",
                },
              }}
              render={({ field }) => (
                <TextInput
                  {...field}
                  error={!!get(errors, "countOfLastAlerts.message")}
                  errorMessage={get(errors, "countOfLastAlerts.message")}
                  onBlur={handleThresholdBlur}
                  type="number"
                  placeholder="Value indicating how many alerts to display in widget"
                  required
                />
              )}
            />
          </div>
          <ColumnsSelection
            selectedColumns={presetColumns}
            onChange={(selectedColumns) => setPresetColumns(selectedColumns)}
          ></ColumnsSelection>
        </>
      )}
      <div className="mb-4">
        <div className="flex items-center justify-between">
          <Subtitle>Thresholds</Subtitle>
          <Button
            color="orange"
            variant="secondary"
            type="button"
            onClick={handleAddThreshold}
          >
            +
          </Button>
        </div>
        <div className="mt-4">
          {fields.map((field, index) => (
            <div key={field.id} className="flex items-center space-x-2 mb-2">
              <TextInput
                {...register(`thresholds.${index}.value`, { required: true })}
                onBlur={handleThresholdBlur}
                placeholder="Threshold value"
                type="number"
                required
              />
              <input
                type="color"
                {...register(`thresholds.${index}.color`, { required: true })}
                className="w-10 h-10 p-1 border"
                required
              />
              {fields.length > 1 && (
                <button
                  type="button"
                  onClick={() => remove(index)}
                  className="p-2"
                >
                  <Icon color="orange" icon={Trashcan} className="h-5 w-5" />
                </button>
              )}
            </div>
          ))}
        </div>
      </div>
    </>
  );
};
