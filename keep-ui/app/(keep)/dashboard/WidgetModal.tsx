import React, { useState } from "react";
import Modal from "@/components/ui/Modal";
import { Button, Select, SelectItem, Subtitle, TextInput } from "@tremor/react";
import { WidgetData, WidgetType } from "./types";
import { Controller, get, useForm, useWatch } from "react-hook-form";
import { MetricsWidget } from "@/utils/hooks/useDashboardMetricWidgets";
import { Preset } from "@/entities/presets/model/types";
import { PresetWidgetForm } from "./widget-types/preset/preset-widget-form";
import { MetricWidgetForm } from "./widget-types/metric/metric-widget-form";
import { GenericMetricsWidgetForm } from "./widget-types/generic-metrics/generic-metrics-widget-form";
import { AlertPresetWidgetForm } from "./widget-types/alert-preset/alert-preset-widget-form";

interface WidgetForm {
  widgetName: string;
  widgetType: WidgetType;
}

interface WidgetModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAddWidget: (widget: any) => void;
  onEditWidget: (updatedWidget: WidgetData) => void;
  presets: Preset[];
  editingItem?: WidgetData | null;
  metricWidgets: MetricsWidget[];
}

const WidgetModal: React.FC<WidgetModalProps> = ({
  isOpen,
  onClose,
  onAddWidget,
  onEditWidget,
  presets,
  editingItem,
  metricWidgets,
}) => {
  const [innerFormState, setInnerFormState] = useState<{
    isValid: boolean;
    formValue: any;
  }>({ isValid: false, formValue: {} });

  const {
    control,
    handleSubmit,
    formState: { errors, isValid },
    reset,
  } = useForm<WidgetForm>({
    defaultValues: {
      widgetName: editingItem?.name || "",
      widgetType: editingItem?.widgetType || WidgetType.PRESET,
    },
  });

  const widgetType = useWatch({
    control,
    name: "widgetType",
  });

  const onSubmit = (data: WidgetForm) => {
    if (editingItem) {
      let updatedWidget: WidgetData = {
        ...editingItem,
        name: data.widgetName,
        widgetType: data.widgetType || WidgetType.PRESET, // backwards compatibility
        ...innerFormState.formValue,
      };
      onEditWidget(updatedWidget);
    } else {
      onAddWidget({
        name: data.widgetName,
        widgetType: data.widgetType || WidgetType.PRESET, // backwards compatibility
        ...innerFormState.formValue,
      });
      // cleanup form
      reset({
        widgetName: "",
        widgetType: WidgetType.PRESET,
      });
    }
    onClose();
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={editingItem ? "Edit Widget" : "Add Widget"}
    >
      <form onSubmit={handleSubmit(onSubmit)}>
        <div className="mb-4 mt-2">
          <Subtitle>Widget Name</Subtitle>
          <Controller
            name="widgetName"
            control={control}
            rules={{
              required: { value: true, message: "Widget name is required" },
            }}
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
          <Subtitle>Widget Type</Subtitle>
          <Controller
            name="widgetType"
            control={control}
            rules={{
              required: {
                value: true,
                message: "Preset selection is required",
              },
            }}
            render={({ field }) => {
              return (
                <Select
                  {...field}
                  placeholder="Select a Widget Type"
                  error={!!get(errors, "selectedWidgetType.message")}
                  errorMessage={get(errors, "selectedWidgetType.message")}
                >
                  {[
                    { key: WidgetType.PRESET, value: "Preset" },
                    {
                      key: WidgetType.GENERICS_METRICS,
                      value: "Generic Metrics",
                    },
                    { key: WidgetType.METRIC, value: "Metric" },
                  ].map(({ key, value }) => (
                    <SelectItem key={key} value={key}>
                      {value}
                    </SelectItem>
                  ))}
                </Select>
              );
            }}
          />
        </div>
        {widgetType === WidgetType.PRESET && (
          <PresetWidgetForm
            editingItem={editingItem}
            presets={presets}
            onChange={(formValue, isValid) =>
              setInnerFormState({ formValue, isValid })
            }
          ></PresetWidgetForm>
        )}
        {widgetType == WidgetType.GENERICS_METRICS && (
          <>
            <GenericMetricsWidgetForm
              editingItem={editingItem}
              onChange={(formValue, isValid) =>
                setInnerFormState({ formValue, isValid })
              }
            ></GenericMetricsWidgetForm>
          </>
        )}
        {widgetType === WidgetType.METRIC && (
          <MetricWidgetForm
            editingItem={editingItem}
            metricWidgets={metricWidgets}
            onChange={(formValue, isValid) =>
              setInnerFormState({ formValue, isValid })
            }
          ></MetricWidgetForm>
        )}
        <Button
          color="orange"
          type="submit"
          disabled={!isValid || !innerFormState.isValid}
        >
          {editingItem ? "Update Widget" : "Add Widget"}
        </Button>
      </form>
    </Modal>
  );
};

export default WidgetModal;
