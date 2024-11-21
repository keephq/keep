import React, { ChangeEvent, useEffect, useState } from "react";
import Modal from "@/components/ui/Modal";
import {
  Button,
  Icon,
  Select,
  SelectItem,
  Subtitle,
  TextInput,
} from "@tremor/react";
import { Trashcan } from "components/icons";
import { GenericsMetrics, Threshold, WidgetData, WidgetType } from "./types";
import { Preset } from "@/app/(keep)/alerts/models";
import { Controller, get, useForm, useWatch } from "react-hook-form";
import { MetricsWidget } from "@/utils/hooks/useDashboardMetricWidgets";

interface WidgetForm {
  widgetName: string;
  selectedPreset: string;
  thresholds: Threshold[];
  widgetType: WidgetType;
  selectedMetricWidget: string;
  selectedGenericMetrics: string;
}

interface WidgetModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAddWidget: (
    name: string,
    widgetType: WidgetType,
    preset?: Preset,
    thresholds?: Threshold[],
    metric?: MetricsWidget,
    genericMetrics?: GenericsMetrics
  ) => void;
  onEditWidget: (updatedWidget: WidgetData) => void;
  presets: Preset[];
  editingItem?: WidgetData | null;
  metricWidgets: MetricsWidget[];
}

const GENERIC_METRICS = [
  {
    key: "alert_quality",
    label: "Alert Quality",
    widgetType: "table",
    meta: {
      defaultFilters: { fields: "severity" },
    },
  },
] as GenericsMetrics[];

const WidgetModal: React.FC<WidgetModalProps> = ({
  isOpen,
  onClose,
  onAddWidget,
  onEditWidget,
  presets,
  editingItem,
  metricWidgets,
}) => {
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
  } = useForm<WidgetForm>({
    defaultValues: {
      widgetName: "",
      selectedPreset: "",
      thresholds: thresholds,
      widgetType: WidgetType.PRESET,
      selectedGenericMetrics: "",
    },
  });

  const widgetType = useWatch({
    control,
    name: "widgetType",
  });

  useEffect(() => {
    if (editingItem) {
      setValue("widgetName", editingItem.name);
      setValue("widgetType", editingItem.widgetType);

      if (editingItem.thresholds) {
        setThresholds(editingItem.thresholds);
      }
      setValue("selectedPreset", editingItem?.preset?.id ?? "");
      setValue("selectedMetricWidget", editingItem?.metric?.id ?? "");
      setValue(
        "selectedGenericMetrics",
        editingItem?.genericMetrics?.key ?? ""
      );
    } else {
      reset({
        widgetName: "",
        selectedPreset: "",
        selectedMetricWidget: "",
        selectedGenericMetrics: "",
        thresholds: thresholds,
        widgetType: WidgetType.PRESET,
      });
    }
  }, [editingItem, setValue, reset]);

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

  const deepClone = (obj: GenericsMetrics | undefined) => {
    if (!obj) {
      return obj;
    }
    return JSON.parse(JSON.stringify(obj)) as GenericsMetrics;
  };

  const onSubmit = (data: WidgetForm) => {
    const preset = presets.find((p) => p.id === data.selectedPreset);
    const metric = metricWidgets.find(
      (p) => p.id === data.selectedMetricWidget
    );
    if (preset || data.selectedGenericMetrics) {
      const formattedThresholds = thresholds.map((t) => ({
        ...t,
        value: parseInt(t.value.toString(), 10) || 0,
      }));

      if (editingItem) {
        let updatedWidget: WidgetData = {
          ...editingItem,
          name: data.widgetName,
          widgetType: data.widgetType || WidgetType.PRESET, // backwards compatibility
          preset,
          thresholds: formattedThresholds,
          genericMetrics: editingItem.genericMetrics,
        };
        onEditWidget(updatedWidget);
      } else {
        onAddWidget(
          data.widgetName,
          data.widgetType,
          preset,
          formattedThresholds,
          undefined,
          deepClone(
            GENERIC_METRICS.find((g) => g.key === data.selectedGenericMetrics)
          )
        );
        // cleanup form
        setThresholds([
          { value: 0, color: "#22c55e" }, // Green
          { value: 20, color: "#ef4444" }, // Red
        ]);
        reset({
          widgetName: "",
          selectedPreset: "",
          thresholds: thresholds,
          selectedGenericMetrics: "",
          widgetType: WidgetType.PRESET,
        });
      }
      onClose();
    }
    if (metric) {
      if (editingItem) {
        const updatedWidget: WidgetData = {
          ...editingItem,
          name: data.widgetName,
          widgetType: data.widgetType,
        };
        onEditWidget(updatedWidget);
      } else {
        onAddWidget(
          data.widgetName,
          data.widgetType,
          undefined,
          undefined,
          metric,
          undefined
        );
        reset({
          widgetName: "",
          selectedPreset: "",
          widgetType: WidgetType.PRESET,
          thresholds: thresholds,
        });
      }
      onClose();
    }
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
        {widgetType === WidgetType.PRESET ? (
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
                        <Icon
                          color="orange"
                          icon={Trashcan}
                          className="h-5 w-5"
                        />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </>
        ) : widgetType === WidgetType.GENERICS_METRICS ? (
          <>
            <div className="mb-4 mt-2">
              <Subtitle>Generic Metrics</Subtitle>
              <Controller
                name="selectedGenericMetrics"
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
                    placeholder="Select a Generic Metrics"
                    error={!!get(errors, "selectedGenericMetrics.message")}
                    errorMessage={get(errors, "selectedGenericMetrics.message")}
                  >
                    {GENERIC_METRICS.map((metrics) => (
                      <SelectItem key={metrics.key} value={metrics.key}>
                        {metrics.label}
                      </SelectItem>
                    ))}
                  </Select>
                )}
              />
            </div>
          </>
        ) : (
          <div className="mb-4 mt-2">
            <Subtitle>Widget</Subtitle>
            <Controller
              name="selectedMetricWidget"
              control={control}
              render={({ field }) => (
                <Select
                  {...field}
                  placeholder="Select a metric widget"
                  error={!!get(errors, "selectedMetricWidget.message")}
                  errorMessage={get(errors, "selectedMetricWidget.message")}
                >
                  {metricWidgets.map((widget) => (
                    <SelectItem key={widget.id} value={widget.id}>
                      {widget.name}
                    </SelectItem>
                  ))}
                </Select>
              )}
            />
          </div>
        )}
        <Button color="orange" type="submit">
          {editingItem ? "Update Widget" : "Add Widget"}
        </Button>
      </form>
    </Modal>
  );
};

export default WidgetModal;
