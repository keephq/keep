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
import { Control, Controller } from "react-hook-form";

export interface PresetWidgetFormProps {
  presets: Preset[];
  control: Control<any, any>;
}

export const PresetWidgetForm: React.FC<
  PresetWidgetFormProps
> = ({}: PresetWidgetFormProps) => {
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
