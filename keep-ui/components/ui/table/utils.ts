// Styles to make sticky column pinning work!
import { Column } from "@tanstack/react-table";
import { CSSProperties } from "react";
import clsx from "clsx";

export const getCommonPinningStylesAndClassNames = (
  column: Column<any>
): { style: CSSProperties; className: string } => {
  const isPinned = column.getIsPinned();
  const isLastLeftPinnedColumn =
    isPinned === "left" && column.getIsLastColumn("left");
  const isFirstRightPinnedColumn =
    isPinned === "right" && column.getIsFirstColumn("right");

  return {
    style: {
      left: isPinned === "left" ? `${column.getStart("left")}px` : undefined,
      right: isPinned === "right" ? `${column.getAfter("right")}px` : undefined,
      width: column.getSize(),
      animationTimeline: "scroll(inline)",
    },
    className: clsx(
      "bg-tremor-background",
      isPinned ? "sticky" : "relative",
      isLastLeftPinnedColumn
        ? "animate-scroll-shadow-left"
        : isFirstRightPinnedColumn
          ? "animate-scroll-shadow-right"
          : undefined,
      isPinned ? "z-[2]" : ""
    ),
  };
};
