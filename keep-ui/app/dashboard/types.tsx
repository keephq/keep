import {Preset} from "app/alerts/models";
import {MetricsWidget} from "@/utils/hooks/useDashboardMetricWidgets";

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

export enum WidgetType {
  PRESET = 'PRESET',
  METRIC = 'METRIC'
}

export interface WidgetData extends LayoutItem {
  widgetType: WidgetType;
  thresholds?: Threshold[];
  preset?: Preset;
  metric?: MetricsWidget;
  name: string;
}

export interface Threshold {
  value: number;
  color: string;
}
