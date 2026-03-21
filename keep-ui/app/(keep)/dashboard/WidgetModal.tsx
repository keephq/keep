import { useI18n } from "@/i18n/hooks/useI18n";
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

const widgetTypeOptions = [
  { key: WidgetType.PRESET, value: "Preset" },
  {
    key: WidgetType.GENERICS_METRICS,
    value: "Generic Metrics",
  },
  { key: WidgetType.METRIC, value: "Metric" },
];

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
  const { t } = useI18n();
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
      title={editingItem ? t("dashboard.widget.editWidget") : t("dashboard.widget.addWidget")}
    >
      <form onSubmit={handleSubmit(onSubmit)}>
        <div className="mb-4 mt-2">
          <Subtitle>{t("dashboard.widget.widgetName")}</Subtitle>
          <Controller
            name="widgetName"
            control={control}
            rules={{
              required: { value: true, message: t("dashboard.widget.nameRequired") },
            }}
            render={({ field }) => (
              <TextInput
                {...field}
                placeholder={t("dashboard.widget.namePlaceholder")}
                error={!!get(errors, "widgetName.message")}
                errorMessage={get(errors, "widgetName.message")}
              />
            )}
          />
        </div>
        <div className="mb-4 mt-2">
          <Subtitle>{t("dashboard.widget.widgetType")}</Subtitle>
          <Controller
            name="widgetType"
            control={control}
            rules={{
              required: {
                value: true,
                message: t("dashboard.widget.typeRequired"),
              },
            }}
            render={({ field }) => {
              return (
                <Select
                  {...field}
                  placeholder={t("dashboard.widget.selectType")}
                  error={!!get(errors, "selectedWidgetType.message")}
                  errorMessage={get(errors, "selectedWidgetType.message")}
                >
                  {widgetTypeOptions.map(({ key, value }) => (
                    <SelectItem key={key} value={key}>
                      {t(`dashboard.widget.types.${key}`)}
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
          {editingItem ? t("dashboard.widget.updateWidget") : t("dashboard.widget.addWidget")}
        </Button>
      </form>
    </Modal>
  );
};

export default WidgetModal;
