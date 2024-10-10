import { Preset } from "app/alerts/models";
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

  export interface WidgetData extends LayoutItem {
    thresholds: Threshold[];
    preset: Preset | null;
    name: string;
    widgetType?:string;
    genericMetrics?: string;
  }

  export interface Threshold {
    value: number;
    color: string;
  }
