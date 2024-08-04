import { MarkerType } from "@xyflow/react";

export const nodeWidth = 220;
export const nodeHeight = 80;

// Edge No Hover
export const edgeLabelBgStyleNoHover = {
  strokeWidth: 1,
  strokeDasharray: "5,5",
  stroke: "#b1b1b7", // default graph stroke line color
};
export const edgeLabelBgBorderRadiusNoHover = 10;
export const edgeLabelBgPaddingNoHover: [number, number] = [10, 5];
export const edgeMarkerEndNoHover = {
  type: MarkerType.ArrowClosed,
};

// Edge Hover
export const edgeLabelBgStyleHover = {
  ...edgeLabelBgStyleNoHover,
  stroke: "none",
  fill: "orange",
  color: "white",
};
export const edgeMarkerEndHover = {
  ...edgeMarkerEndNoHover,
  color: "orange",
};
