"use client";

import clsx from "clsx";
import React, { useState, useCallback, useEffect } from "react";

interface ResizableColumnsProps {
  initialLeftWidth?: number;
  children: React.ReactNode;
  leftChildClassName?: string;
  rightChildClassName?: string;
}

export const ResizableColumns = ({
  initialLeftWidth = 50,
  leftChildClassName,
  rightChildClassName,
  children,
}: ResizableColumnsProps) => {
  if (React.Children.count(children) !== 2) {
    throw new Error("ResizableColumns must have exactly two children");
  }
  const [leftChild, rightChild] = React.Children.toArray(children);
  const [isDragging, setIsDragging] = useState(false);
  const [leftWidth, setLeftWidth] = useState(initialLeftWidth);

  // Memoize the left child
  const MemoizedLeftChild = React.useMemo(
    () => (
      <div
        className={clsx("min-w-0 p-px", leftChildClassName)}
        style={{ width: `${leftWidth}%` }}
      >
        {leftChild}
      </div>
    ),
    [leftChild, leftWidth, leftChildClassName]
  );

  // Memoize the right child
  const MemoizedRightChild = React.useMemo(
    () => (
      <div className={clsx("flex-1 min-w-0 p-px", rightChildClassName)}>
        {rightChild}
      </div>
    ),
    [rightChild, rightChildClassName]
  );

  const startDragging = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    setIsDragging(true);
  }, []);

  const stopDragging = useCallback(() => {
    setIsDragging(false);
  }, []);

  const onMouseMove = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (isDragging) {
        const containerRect = e.currentTarget.getBoundingClientRect();
        const newWidth =
          ((e.clientX - containerRect.left) / containerRect.width) * 100;
        setLeftWidth(Math.min(Math.max(newWidth, 20), 80));
      }
    },
    [isDragging]
  );

  useEffect(() => {
    if (isDragging) {
      document.addEventListener("mouseup", stopDragging);
      document.addEventListener("mouseleave", stopDragging);
    }
    return () => {
      document.removeEventListener("mouseup", stopDragging);
      document.removeEventListener("mouseleave", stopDragging);
    };
  }, [isDragging, stopDragging]);

  return (
    <div className="flex h-full w-full" onMouseMove={onMouseMove}>
      {MemoizedLeftChild}

      <div
        className="w-1 bg-gray-200 hover:bg-blue-500 cursor-col-resize transition-colors shrink-0"
        onMouseDown={startDragging}
      />

      {MemoizedRightChild}
    </div>
  );
};
