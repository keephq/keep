import React from "react";
import { XMarkIcon } from "@heroicons/react/24/outline";
import { Button } from "@tremor/react";

type NodeLimitWarningProps = {
  totalNodes: number;
  displayedNodes: number;
  onClose: () => void;
  onShowAll?: () => void;
};

export const NodeLimitWarning: React.FC<NodeLimitWarningProps> = ({
  totalNodes,
  displayedNodes,
  onClose,
  onShowAll,
}) => {
  return (
    <div className="w-full bg-amber-50 border-b border-amber-300 p-2 mb-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-medium text-amber-800">Limited View</h3>
          <p className="text-sm text-amber-700">
            For performance reasons, only {displayedNodes} out of {totalNodes}{" "}
            nodes are displayed.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {onShowAll && (
            <Button
              size="xs"
              color="amber"
              variant="secondary"
              onClick={onShowAll}
              className="text-xs"
            >
              Show All (May Affect Performance)
            </Button>
          )}
          <button
            type="button"
            className="text-amber-400 hover:text-amber-500"
            onClick={onClose}
          >
            <XMarkIcon className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>
      </div>
    </div>
  );
};
