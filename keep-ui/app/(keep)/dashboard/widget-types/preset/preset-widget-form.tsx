import { Trashcan } from "@/components/icons";
import { Preset } from "@/entities/presets/model";
import {
  Button,
  Icon,
  Select,
  SelectItem,
  Subtitle,
  TextInput,
} from "@tremor/react";
import { ChangeEvent, useEffect, useState } from "react";
import { Controller, get, useForm, useWatch, Control } from "react-hook-form";
import { Threshold, WidgetType } from "../../types";

interface PresetForm {
  selectedPreset: string;
  thresholds: Threshold[];
}

export interface PresetWidgetFormProps {
  editingItem?: any;
  presets: Preset[];
  onChange: (formState: any) => void;
}

export const PresetWidgetForm: React.FC<PresetWidgetFormProps> = ({
  editingItem,
  presets,
  onChange,
}: PresetWidgetFormProps) => {
  const [thresholds, setThresholds] = useState<Threshold[]>([
    { value: 0, color: "#22c55e" }, // Green
    { value: 20, color: "#ef4444" }, // Red
  ]);

  const {
    control,
    handleSubmit,
    setValue,
    formState: { errors },
    reset,
    getValues,
  } = useForm<PresetForm>({
    defaultValues: {
      selectedPreset: editingItem?.preset?.id,
      thresholds: editingItem?.thresholds || thresholds,
    },
  });

  const formValues = useWatch({ control });

  useEffect(() => {
    const preset = presets.find((p) => p.id === formValues.selectedPreset);
    const formattedThresholds = thresholds.map((t) => ({
      ...t,
      value: parseInt(t.value.toString(), 10) || 0,
    }));
    onChange({ preset, thresholds: formattedThresholds });
  }, [formValues, thresholds]);

  const handleThresholdChange = (
    index: number,
    field: "value" | "color",
    e: ChangeEvent<HTMLInputElement>
  ) => {
    const value = field === "value" ? e.target.value : e.target.value;
    const updatedThresholds = thresholds.map((t, i) =>
      i === index ? { ...t, [field]: value } : t
    );
    setThresholds(updatedThresholds);
  };

  const handleThresholdBlur = () => {
    setThresholds((prevThresholds) => {
      return prevThresholds
        .map((t) => ({
          ...t,
          value: parseInt(t.value.toString(), 10) || 0,
        }))
        .sort((a, b) => a.value - b.value);
    });
  };

  const handleAddThreshold = () => {
    const maxThreshold = Math.max(...thresholds.map((t) => t.value), 0);
    setThresholds([
      ...thresholds,
      { value: maxThreshold + 10, color: "#000000" },
    ]);
  };

  const handleRemoveThreshold = (index: number) => {
    setThresholds(thresholds.filter((_, i) => i !== index));
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
          {thresholds.map((threshold, index) => (
            <div key={index} className="flex items-center space-x-2 mb-2">
              <TextInput
                value={threshold.value.toString()}
                onChange={(e) => handleThresholdChange(index, "value", e)}
                onBlur={handleThresholdBlur}
                placeholder="Threshold value"
                required
              />
              <input
                type="color"
                value={threshold.color}
                onChange={(e) => handleThresholdChange(index, "color", e)}
                className="w-10 h-10 p-1 border"
                required
              />
              {thresholds.length > 1 && (
                <button
                  type="button"
                  onClick={() => handleRemoveThreshold(index)}
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
