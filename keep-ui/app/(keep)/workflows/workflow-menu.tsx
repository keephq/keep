import { EllipsisHorizontalIcon } from "@heroicons/react/20/solid";
import {
  EyeIcon,
  PlayIcon,
  TrashIcon,
  WrenchIcon,
} from "@heroicons/react/24/outline";
import { DownloadIcon } from "@radix-ui/react-icons";
import React from "react";
import { DropdownMenu } from "@/shared/ui";

interface WorkflowMenuProps {
  onDelete?: () => Promise<void>;
  onRun?: () => Promise<void>;
  onView?: () => void;
  onDownload?: () => void;
  onBuilder?: () => void;
  isRunButtonDisabled: boolean;
  runButtonToolTip?: string;
  provisioned?: boolean;
}

export default function WorkflowMenu({
  onDelete,
  onRun,
  onView,
  onDownload,
  onBuilder,
  isRunButtonDisabled,
  runButtonToolTip,
  provisioned,
}: WorkflowMenuProps) {
  return (
    <div className="js-dont-propagate">
      <DropdownMenu.Menu icon={EllipsisHorizontalIcon} label="">
        <DropdownMenu.Item
          icon={PlayIcon}
          label="Run workflow"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onRun?.();
          }}
          title={runButtonToolTip}
          disabled={isRunButtonDisabled}
        />
        <DropdownMenu.Item
          icon={DownloadIcon}
          label="Download"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onDownload?.();
          }}
        />
        <DropdownMenu.Item
          icon={EyeIcon}
          label="Last executions"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onView?.();
          }}
        />
        <DropdownMenu.Item
          icon={WrenchIcon}
          label="Open in builder"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onBuilder?.();
          }}
        />
        <DropdownMenu.Item
          icon={TrashIcon}
          label="Delete"
          variant="destructive"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onDelete?.();
          }}
          disabled={provisioned}
          title={provisioned ? "Cannot delete a provisioned workflow" : ""}
        />
      </DropdownMenu.Menu>
    </div>
  );
}
