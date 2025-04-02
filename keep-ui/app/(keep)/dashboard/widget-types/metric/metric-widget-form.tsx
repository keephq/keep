import { Select, SelectItem, Subtitle } from "@tremor/react";
import { useEffect } from "react";
import { Controller, get, useForm, useWatch } from "react-hook-form";
import { MetricsWidget } from "@/utils/hooks/useDashboardMetricWidgets";

interface PresetForm {
  selectedMetricWidget: string;
}

export interface MetricWidgetFormProps {
  metricWidgets: MetricsWidget[];
  editingItem?: any;
  onChange: (formState: any, isValid: boolean) => void;
}

export const MetricWidgetForm: React.FC<MetricWidgetFormProps> = ({
  metricWidgets,
  editingItem,
  onChange,
}) => {
  const {
    control,
    formState: { errors, isValid },
  } = useForm<PresetForm>({
    defaultValues: {
      selectedMetricWidget: editingItem?.metric?.id ?? "",
    },
  });
  const formValues = useWatch({ control });

  useEffect(() => {
    const metric = metricWidgets.find(
      (p) => p.id === formValues.selectedMetricWidget
    );
    onChange({ metric }, isValid);
  }, [formValues]);

  return (
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
  );
};
