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

export interface WidgetData extends LayoutItem {
  thresholds?: Threshold[];
  preset?: Preset;
  name: string;
  widgetType: WidgetType;
  genericMetrics?: GenericsMetrics;
  metric?: MetricsWidget;
}

export interface Threshold {
  value: number;
  color: string;
}
