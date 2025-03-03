// Styles to make sticky column pinning work!
import { Column } from "@tanstack/react-table";
import { CSSProperties } from "react";
import clsx from "clsx";

export const getCommonPinningStylesAndClassNames = (
  column: Column<any>,
  leftPinnedColumnsCount?: number,
  rightPinnedColumnsCount?: number
): { style: CSSProperties; className: string } => {
  const isPinned = column.getIsPinned();
  const isLastLeftPinnedColumn =
    isPinned === "left" && column.getIsLastColumn("left");

  const zIndex = (() => {
    if (isPinned === "left") {
      return leftPinnedColumnsCount
        ? leftPinnedColumnsCount + 1 - column.getPinnedIndex()
        : 1;
    }
    if (isPinned === "right") {
      return rightPinnedColumnsCount
        ? rightPinnedColumnsCount + 1 - column.getPinnedIndex()
        : 1;
    }
    return undefined;
  })();

  return {
    style: {
      left: isPinned === "left" ? `${column.getStart("left")}px` : undefined,
      right: isPinned === "right" ? `${column.getAfter("right")}px` : undefined,
      width: column.getSize(),
      animationTimeline: "scroll(inline)",
      zIndex,
    },
    className: clsx(
      "bg-tremor-background",
      isPinned ? "sticky" : "relative",
      isLastLeftPinnedColumn ? "animate-scroll-shadow-left" : undefined
    ),
  };
};
