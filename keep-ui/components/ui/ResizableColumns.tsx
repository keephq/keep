import React, { useState, useCallback, useEffect } from "react";

interface ResizableColumnsProps {
  leftChild: React.ReactNode;
  rightChild: React.ReactNode;
  leftClassName?: string;
  rightClassName?: string;
  initialLeftWidth?: number;
}

const ResizableColumns = ({
  leftChild,
  leftClassName = "bg-gray-50 p-4 overflow-auto",
  rightChild,
  rightClassName = "flex-1 bg-white p-4 overflow-auto",
  initialLeftWidth = 50,
}: ResizableColumnsProps) => {
  const [isDragging, setIsDragging] = useState(false);
  const [leftWidth, setLeftWidth] = useState(initialLeftWidth);

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
    <div
      className="flex h-full w-full overflow-hidden rounded"
      onMouseMove={onMouseMove}
    >
      <div className={leftClassName} style={{ width: `${leftWidth}%` }}>
        {leftChild}
      </div>

      <div
        className="w-1 bg-gray-200 hover:bg-orange-500 cursor-col-resize transition-colors mt-2.5"
        onMouseDown={startDragging}
      />

      <div
        className={rightClassName}
        style={{ flexBasis: `${100 - leftWidth}%` }}
      >
        {rightChild}
      </div>
    </div>
  );
};

export default ResizableColumns;
