import React, { useState, useEffect, ChangeEvent, FormEvent } from "react";
import Modal from "@/components/ui/Modal";
import { Button, Subtitle, TextInput, Select, SelectItem, Icon } from "@tremor/react";
import { Trashcan } from "components/icons";
import { Threshold, WidgetData } from "./types";
import { Preset } from "app/alerts/models";
import { useForm, Controller, get } from "react-hook-form";

interface WidgetForm {
  widgetName: string;
  selectedPreset: string;
  thresholds: Threshold[];
}

interface WidgetModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAddWidget: (preset: Preset, thresholds: Threshold[], name: string) => void;
  onEditWidget: (updatedWidget: WidgetData) => void;
  presets: Preset[];
  editingItem?: WidgetData | null;
}

const WidgetModal: React.FC<WidgetModalProps> = ({ isOpen, onClose, onAddWidget, onEditWidget, presets, editingItem }) => {
  const [thresholds, setThresholds] = useState<Threshold[]>([
    { value: 0, color: '#22c55e' }, // Green
    { value: 20, color: '#ef4444' } // Red
  ]);

  const { control, handleSubmit, setValue, formState: { errors }, reset } = useForm<WidgetForm>({
    defaultValues: {
      widgetName: '',
      selectedPreset: '',
      thresholds: thresholds,
    }
  });

  useEffect(() => {
    if (editingItem) {
      setValue('widgetName', editingItem.name);
      setValue('selectedPreset', editingItem.preset.id);
      setThresholds(editingItem.thresholds);
    } else {
      reset({
        widgetName: '',
        selectedPreset: '',
        thresholds: thresholds,
      });
    }
  }, [editingItem, setValue, reset]);

  const handleThresholdChange = (index: number, field: 'value' | 'color', e: ChangeEvent<HTMLInputElement>) => {
    const value = field === 'value' ? e.target.value : e.target.value;
    const updatedThresholds = thresholds.map((t, i) => i === index ? { ...t, [field]: value } : t);
    setThresholds(updatedThresholds);
  };

  const handleThresholdBlur = () => {
    setThresholds(prevThresholds => {
      return prevThresholds
        .map(t => ({
          ...t,
          value: parseInt(t.value.toString(), 10) || 0
        }))
        .sort((a, b) => a.value - b.value);
    });
  };

  const handleAddThreshold = () => {
    const maxThreshold = Math.max(...thresholds.map(t => t.value), 0);
    setThresholds([...thresholds, { value: maxThreshold + 10, color: '#000000' }]);
  };

  const handleRemoveThreshold = (index: number) => {
    setThresholds(thresholds.filter((_, i) => i !== index));
  };

  const onSubmit = (data: WidgetForm) => {
    const preset = presets.find(p => p.id === data.selectedPreset);
    if (preset) {
      const formattedThresholds = thresholds.map(t => ({
        ...t,
        value: parseInt(t.value.toString(), 10) || 0
      }));

      if (editingItem) {
        const updatedWidget: WidgetData = {
          ...editingItem,
          name: data.widgetName,
          preset,
          thresholds: formattedThresholds,
        };
        onEditWidget(updatedWidget);
      } else {
        onAddWidget(preset, formattedThresholds, data.widgetName);
        // cleanup form
        setThresholds([
          { value: 0, color: '#22c55e' }, // Green
          { value: 20, color: '#ef4444' } // Red
        ]);
        reset({
          widgetName: '',
          selectedPreset: '',
          thresholds: thresholds,
        });
      }
      onClose();
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={editingItem ? "Edit Widget" : "Add Widget"}>
      <form onSubmit={handleSubmit(onSubmit)}>
        <div className="mb-4 mt-2">
          <Subtitle>Widget Name</Subtitle>
          <Controller
            name="widgetName"
            control={control}
            rules={{ required: { value: true, message: "Widget name is required" } }}
            render={({ field }) => (
              <TextInput
                {...field}
                placeholder="Enter widget name"
                error={!!get(errors, "widgetName.message")}
                errorMessage={get(errors, "widgetName.message")}
              />
            )}
          />
        </div>
        <div className="mb-4 mt-2">
          <Subtitle>Preset</Subtitle>
          <Controller
            name="selectedPreset"
            control={control}
            rules={{ required: { value: true, message: "Preset selection is required" } }}
            render={({ field }) => (
              <Select
                {...field}
                placeholder="Select a preset"
                error={!!get(errors, "selectedPreset.message")}
                errorMessage={get(errors, "selectedPreset.message")}
              >
                {presets.map(preset => (
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
            <Button color="orange" variant="secondary" type="button" onClick={handleAddThreshold}>
              +
            </Button>
          </div>
          <div className="mt-4">
            {thresholds.map((threshold, index) => (
              <div key={index} className="flex items-center space-x-2 mb-2">
                <TextInput
                  value={threshold.value.toString()}
                  onChange={(e) => handleThresholdChange(index, 'value', e)}
                  onBlur={handleThresholdBlur}
                  placeholder="Threshold value"
                  required
                />
                <input
                  type="color"
                  value={threshold.color}
                  onChange={(e) => handleThresholdChange(index, 'color', e)}
                  className="w-10 h-10 p-1 border"
                  required
                />
                {thresholds.length > 1 && (
                  <button type="button" onClick={() => handleRemoveThreshold(index)} className="p-2">
                    <Icon color="orange" icon={Trashcan} className="h-5 w-5" />
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
        <Button color="orange" type="submit">{editingItem ? "Update Widget" : "Add Widget"}</Button>
      </form>
    </Modal>
  );
};

export default WidgetModal;
