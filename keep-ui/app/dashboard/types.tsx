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

 export interface GenericsMertics {
    key: string;
    label: string;
    widgetType: "table" | "chart";
    meta: {
      defaultFilters: {
        [key: string]: string|string[];
      },
    }
  }

  export interface WidgetData extends LayoutItem {
    thresholds: Threshold[];
    preset: Preset | null;
    name: string;
    widgetType?:string;
    genericMetrics?: GenericsMertics| null;
  }

  export interface Threshold {
    value: number;
    color: string;
  }
