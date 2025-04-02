import { Trashcan } from "@/components/icons";
import { Preset, usePresets } from "@/entities/presets/model";
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
import { LayoutItem, Threshold, WidgetType } from "../../types";

interface PresetForm {
  selectedPresetId: string;
}

export interface AlertPresetWidgetFormProps {
  editingItem?: any;
  onChange: (formState: any, isValid: boolean) => void;
}

export const AlertPresetWidgetForm: React.FC<AlertPresetWidgetFormProps> = ({
  editingItem,
  onChange,
}: AlertPresetWidgetFormProps) => {
  const { dynamicPresets, staticPresets } = usePresets();

  const {
    control,
    formState: { errors, isValid },
  } = useForm<PresetForm>();

  const formValues = useWatch({ control });

  function getLayoutValues(): LayoutItem {
    if (editingItem) {
      return {} as LayoutItem;
    }

    return {
      w: 3,
      h: 3,
      minW: 2,
      minH: 3,
      static: false,
    } as LayoutItem;
  }

  useEffect(() => {
    onChange(
      {
        ...getLayoutValues(),
        alertPreset: { presetId: formValues.selectedPresetId },
      },
      isValid
    );
  }, [formValues]);

  return (
    <>
      <div className="mb-4 mt-2">
        <Subtitle>Preset</Subtitle>
        <Controller
          name="selectedPresetId"
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
              placeholder="Alerts preset"
              error={!!get(errors, "selectedPresetId.message")}
              errorMessage={get(errors, "selectedPresetId.message")}
            >
              {dynamicPresets.map((preset) => (
                <SelectItem key={preset.id} value={preset.id}>
                  {preset.name}
                </SelectItem>
              ))}
            </Select>
          )}
        />
      </div>
    </>
  );
};
