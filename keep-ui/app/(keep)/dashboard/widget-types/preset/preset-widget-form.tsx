import { useI18n } from "@/i18n/hooks/useI18n";
import { Trashcan } from "@/components/icons";
import { Preset } from "@/entities/presets/model";
import {
  Button,
  Icon,
  Select,
  SelectItem,
  Subtitle,
  TextInput,
  Switch,
} from "@tremor/react";
import { useEffect, useMemo, useState } from "react";
import {
  Controller,
  get,
  useForm,
  useWatch,
  useFieldArray,
} from "react-hook-form";
import { LayoutItem, Threshold, PresetPanelType } from "../../types";
import ColumnsSelection from "./columns-selection";

interface PresetForm {
  selectedPreset: string;
  countOfLastAlerts: string;
  thresholds: Threshold[];
  presetPanelType: PresetPanelType;
  showFiringOnly: boolean;
  customLink?: string;
}

export interface PresetWidgetFormProps {
  editingItem?: any;
  presets: Preset[];
  onChange: (formState: any, isValid: boolean) => void;
}

export const PresetWidgetForm: React.FC<PresetWidgetFormProps> = ({
  editingItem,
  presets,
  onChange,
}: PresetWidgetFormProps) => {
  const { t } = useI18n();
  const {
    control,
    formState: { errors, isValid },
    register,
  } = useForm<PresetForm>({
    defaultValues: {
      selectedPreset: editingItem?.preset?.id,
      countOfLastAlerts: editingItem
        ? editingItem.preset.countOfLastAlerts || 0
        : 5,
      thresholds: editingItem?.thresholds || [
        { value: 0, color: "#10b981" }, // Bold emerald green
        { value: 20, color: "#dc2626" }, // Bold red
      ],
      presetPanelType: editingItem?.presetPanelType || PresetPanelType.ALERT_TABLE,
      showFiringOnly: editingItem?.showFiringOnly ?? false,
      customLink: editingItem?.customLink || "",
    },
  });
  const [presetColumns, setPresetColumns] = useState<string[] | undefined>(
    editingItem ? editingItem.presetColumns : undefined
  );

  const { fields, append, remove, move, replace } = useFieldArray({
    control,
    name: "thresholds",
  });

  const formValues = useWatch({ control });

  const normalizedFormValues = useMemo(() => {
    return {
      countOfLastAlerts: parseInt(formValues.countOfLastAlerts || "0"),
      selectedPreset: presets.find((p) => p.id === formValues.selectedPreset),
      presetColumns,
      thresholds: formValues.thresholds?.map((t) => ({
        ...t,
        value: parseInt(t.value?.toString() as string, 10) || 0,
      })),
      presetPanelType: formValues.presetPanelType || PresetPanelType.ALERT_TABLE,
      showFiringOnly: formValues.showFiringOnly ?? false,
      customLink: formValues.customLink || "",
    };
  }, [formValues, presetColumns]);

  function getLayoutValues(): LayoutItem {
    if (editingItem) {
      return {} as LayoutItem;
    }

    const isAlertTable = normalizedFormValues.presetPanelType === PresetPanelType.ALERT_TABLE;
    const isAlertCountPanel = normalizedFormValues.presetPanelType === PresetPanelType.ALERT_COUNT_PANEL;
    
    if (isAlertCountPanel) {
      // Narrower, more compact layout for count panels with no minimum width
      return {
        w: 4,
        h: 3,
        minW: 0,
        minH: 2,
        static: false,
      } as LayoutItem;
    }
    
    // Original layout for alert tables
    const itemHeight = isAlertTable && normalizedFormValues.countOfLastAlerts > 0 ? 6 : 4;
    const itemWidth = isAlertTable && normalizedFormValues.countOfLastAlerts > 0 ? 8 : 6;

    return {
      w: itemWidth,
      h: itemHeight,
      minW: 4,
      minH: 4,
      static: false,
    } as LayoutItem;
  }

  useEffect(() => {
    onChange(
      {
        ...getLayoutValues(),
        preset: {
          ...normalizedFormValues.selectedPreset,
          countOfLastAlerts: normalizedFormValues.countOfLastAlerts,
        },
        presetColumns: normalizedFormValues.presetColumns,
        thresholds: normalizedFormValues.thresholds,
        presetPanelType: normalizedFormValues.presetPanelType,
        showFiringOnly: normalizedFormValues.showFiringOnly,
        customLink: normalizedFormValues.customLink,
      },
      isValid
    );
  }, [normalizedFormValues, isValid]);

  const handleThresholdBlur = () => {
    const reorderedThreesholds = formValues?.thresholds
      ?.map((t) => ({
        ...t,
        value: parseInt(t.value?.toString() as string, 10) || 0,
      }))
      .sort((a, b) => a.value - b.value);
    if (!reorderedThreesholds) {
      return;
    }
    replace(reorderedThreesholds as any);
  };

  const handleAddThreshold = () => {
    const maxThreshold = Math.max(
      ...(formValues.thresholds?.map((t) => t.value) as any),
      0
    );
    append({ value: maxThreshold + 10, color: "#000000" });
  };

  return (
    <>
      <div className="mb-4 mt-2">
        <Subtitle>{t("dashboard.presetWidget.preset")}</Subtitle>
        <Controller
          name="selectedPreset"
          control={control}
          rules={{
            required: {
              value: true,
              message: t("dashboard.presetWidget.presetRequired"),
            },
          }}
          render={({ field }) => (
            <Select
              {...field}
              placeholder={t("dashboard.presetWidget.presetPlaceholder")}
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
      <div className="mb-4 mt-2">
        <Subtitle>{t("dashboard.presetWidget.panelType")}</Subtitle>
        <Controller
          name="presetPanelType"
          control={control}
          rules={{
            required: {
              value: true,
              message: t("dashboard.presetWidget.panelTypeRequired"),
            },
          }}
          render={({ field }) => (
            <Select
              {...field}
              placeholder={t("dashboard.presetWidget.panelTypePlaceholder")}
              error={!!get(errors, "presetPanelType.message")}
              errorMessage={get(errors, "presetPanelType.message")}
            >
              <SelectItem value={PresetPanelType.ALERT_TABLE}>
                {t("dashboard.presetWidget.alertTable")}
              </SelectItem>
              <SelectItem value={PresetPanelType.ALERT_COUNT_PANEL}>
                {t("dashboard.presetWidget.alertCountPanel")}
              </SelectItem>
            </Select>
          )}
        />
      </div>
      {formValues.presetPanelType === PresetPanelType.ALERT_COUNT_PANEL && (
        <>
          <div className="mb-4 mt-2">
            <div className="flex items-center justify-between">
              <Subtitle>{t("dashboard.presetWidget.showFiringOnly")}</Subtitle>
              <Controller
                name="showFiringOnly"
                control={control}
                render={({ field }) => (
                  <Switch
                    checked={field.value}
                    onChange={field.onChange}
                  />
                )}
              />
            </div>
          </div>
          <div className="mb-4 mt-2">
            <Subtitle>{t("dashboard.presetWidget.customLink")}</Subtitle>
            <Controller
              name="customLink"
              control={control}
              render={({ field }) => (
                <TextInput
                  {...field}
                  placeholder={t("dashboard.presetWidget.customLinkPlaceholder")}
                  type="url"
                />
              )}
            />
          </div>
        </>
      )}
      {formValues.presetPanelType === PresetPanelType.ALERT_TABLE && (
        <>
          <div className="mb-4 mt-2">
            <Subtitle>{t("dashboard.presetWidget.lastAlertsCount")}</Subtitle>
            <Controller
              name="countOfLastAlerts"
              control={control}
              rules={{
                required: {
                  value: true,
                  message: t("dashboard.presetWidget.presetRequired"),
                },
              }}
              render={({ field }) => (
                <TextInput
              {...field}
              error={!!get(errors, "countOfLastAlerts.message")}
              errorMessage={get(errors, "countOfLastAlerts.message")}
              onBlur={handleThresholdBlur}
              type="number"
              placeholder={t("dashboard.presetWidget.lastAlertsCountPlaceholder")}
              required
            />
          )}
        />
      </div>
      <ColumnsSelection
        selectedColumns={presetColumns}
        onChange={(selectedColumns) => setPresetColumns(selectedColumns)}
      ></ColumnsSelection>
        </>
      )}
      <div className="mb-4">
        <div className="flex items-center justify-between">
          <Subtitle>{t("dashboard.presetWidget.thresholds")}</Subtitle>
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
          {fields.map((field, index) => (
            <div key={field.id} className="flex items-center space-x-2 mb-2">
              <TextInput
                {...register(`thresholds.${index}.value`, { required: true })}
                onBlur={handleThresholdBlur}
                placeholder={t("dashboard.presetWidget.thresholdValue")}
                type="number"
                required
              />
              <input
                type="color"
                {...register(`thresholds.${index}.color`, { required: true })}
                className="w-10 h-10 p-1 border"
                required
              />
              {fields.length > 1 && (
                <button
                  type="button"
                  onClick={() => remove(index)}
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
