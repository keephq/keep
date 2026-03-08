import { MetricsWidget } from "@/utils/hooks/useDashboardMetricWidgets";
import { Preset } from "@/entities/presets/model/types";

export interface LayoutItem {
  i: string;
  x: number;
  y: number;
  w: number;
  h: number;
  minW?: number;
  minH?: number;
  static: boolean;
}

export interface GenericsMetrics {
  key: string;
  label: string;
  widgetType: "table" | "chart";
  meta: {
    defaultFilters: {
      [key: string]: string | string[];
    };
  };
}

export enum WidgetType {
  PRESET = "PRESET",
  METRIC = "METRIC",
  GENERICS_METRICS = "GENERICS_METRICS",
}

export enum PresetPanelType {
  ALERT_TABLE = "ALERT_TABLE",
  ALERT_COUNT_PANEL = "ALERT_COUNT_PANEL",
  ALERT_TIME_SERIES = "ALERT_TIME_SERIES",
}

export interface WidgetData extends LayoutItem {
  thresholds?: Threshold[];
  preset?: Preset;
  name: string;
  widgetType: WidgetType;
  genericMetrics?: GenericsMetrics;
  metric?: MetricsWidget;
  presetPanelType?: PresetPanelType;
  showFiringOnly?: boolean;
  customLink?: string;
}

export interface Threshold {
  value: number;
  color: string;
}
