import React, { useState, useCallback, useEffect } from "react";

interface ResizableColumnsProps {
  leftChild: React.ReactNode;
  rightChild: React.ReactNode;
  initialLeftWidth?: number;
}

const ResizableColumns = ({
  leftChild,
  rightChild,
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
      <div
        className="bg-gray-50 p-4 overflow-auto"
        style={{ width: `${leftWidth}%` }}
      >
        {leftChild}
      </div>

      <div
        className="w-1 bg-gray-200 hover:bg-blue-500 cursor-col-resize transition-colors"
        onMouseDown={startDragging}
      />

      <div className="flex-1 p-4 overflow-auto">{rightChild}</div>
    </div>
  );
};

export default ResizableColumns;
