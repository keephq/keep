export interface LayoutItem {
  i: string;
  x: number;
  y: number;
  w: number;
  h: number;
  minW?: number;
  minH?: number;
  static?: boolean;
}

export interface AlertDashboardData extends LayoutItem {
  name: string;
}


export interface AlertDashboardDatawithLayout {
  layout: LayoutItem[];
  data: AlertDashboardData[];
}