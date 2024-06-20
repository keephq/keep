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
    preset: Preset;
    name: string;
  }

  export interface Threshold {
    value: number;
    color: string;
  }
