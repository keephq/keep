import { Select, SelectItem, Subtitle } from "@tremor/react";
import { useEffect } from "react";
import { Controller, get, useForm, useWatch } from "react-hook-form";
import { MetricsWidget } from "@/utils/hooks/useDashboardMetricWidgets";
import { GenericsMetrics } from "../../types";

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

interface GenericMetricsForm {
  selectedGenericMetrics: string;
}

export interface GenericMetricsWidgetFormProps {
  editingItem?: any;
  onChange: (formState: any, isValid: boolean) => void;
}

export const GenericMetricsWidgetForm: React.FC<
  GenericMetricsWidgetFormProps
> = ({ editingItem, onChange }) => {
  const {
    control,
    formState: { errors, isValid },
  } = useForm<GenericMetricsForm>({
    defaultValues: {
      selectedGenericMetrics: editingItem?.genericMetrics?.key ?? "",
    },
  });
  const formValues = useWatch({ control });

  const deepClone = (obj: GenericsMetrics | undefined) => {
    if (!obj) {
      return obj;
    }
    return JSON.parse(JSON.stringify(obj)) as GenericsMetrics;
  };

  useEffect(() => {
    const genericMetrics = deepClone(
      GENERIC_METRICS.find((g) => g.key === formValues.selectedGenericMetrics)
    );
    onChange({ genericMetrics }, isValid);
  }, [formValues]);

  return (
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
  );
};
