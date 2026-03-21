import { useI18n } from "@/i18n/hooks/useI18n";
import { Select, SelectItem, Subtitle } from "@tremor/react";
import { useEffect } from "react";
import { Controller, get, useForm, useWatch } from "react-hook-form";
import { MetricsWidget } from "@/utils/hooks/useDashboardMetricWidgets";
import { LayoutItem } from "../../types";

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
  const { t } = useI18n();
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
    onChange({ ...getLayoutValues(), metric }, isValid);
  }, [formValues]);

  function getLayoutValues(): LayoutItem {
    if (editingItem) {
      return {} as LayoutItem;
    }

    return {
      w: 6,
      h: 8,
      minW: 2,
      minH: 7,
      static: false,
    } as LayoutItem;
  }

  return (
    <div className="mb-4 mt-2">
      <Subtitle>{t("dashboard.widget")}</Subtitle>
      <Controller
        name="selectedMetricWidget"
        control={control}
        render={({ field }) => (
          <Select
            {...field}
            placeholder={t("dashboard.selectMetricWidget")}
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
