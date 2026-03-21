import { EllipsisHorizontalIcon } from "@heroicons/react/20/solid";
import {
  EyeIcon,
  PlayIcon,
  TrashIcon,
  WrenchIcon,
  PauseIcon,
  PlayCircleIcon,
} from "@heroicons/react/24/outline";
import { DownloadIcon } from "@radix-ui/react-icons";
import React from "react";
import { DropdownMenu } from "@/shared/ui";
import { useI18n } from "@/i18n/hooks/useI18n";

interface WorkflowMenuProps {
  onDelete?: () => Promise<void>;
  onRun?: () => void;
  onView?: () => void;
  onDownload?: () => void;
  onBuilder?: () => void;
  onToggleState?: () => Promise<void>;
  isRunButtonDisabled: boolean;
  runButtonToolTip?: string;
  provisioned?: boolean;
  isDisabled?: boolean;
}

export default function WorkflowMenu({
  onDelete,
  onRun,
  onView,
  onDownload,
  onBuilder,
  onToggleState,
  isRunButtonDisabled,
  runButtonToolTip,
  provisioned,
  isDisabled,
}: WorkflowMenuProps) {
  const { t } = useI18n();
  return (
    <div className="js-dont-propagate" data-testid="workflow-menu">
      <DropdownMenu.Menu icon={EllipsisHorizontalIcon} label="">
        <DropdownMenu.Item
          icon={PlayIcon}
          label={t("workflows.actions.runWorkflow")}
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
          label={t("workflows.actions.download")}
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onDownload?.();
          }}
        />
        <DropdownMenu.Item
          icon={EyeIcon}
          label={t("workflows.actions.lastExecutions")}
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onView?.();
          }}
        />
        <DropdownMenu.Item
          icon={WrenchIcon}
          label={t("workflows.actions.openInBuilder")}
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onBuilder?.();
          }}
        />
        <DropdownMenu.Item
          icon={isDisabled ? PlayCircleIcon : PauseIcon}
          label={isDisabled ? t("workflows.actions.enableWorkflow") : t("workflows.actions.disableWorkflow")}
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onToggleState?.();
          }}
          disabled={provisioned}
          title={provisioned ? t("workflows.messages.cannotModifyProvisioned") : ""}
        />
        <DropdownMenu.Item
          icon={TrashIcon}
          label={t("common.actions.delete")}
          variant="destructive"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onDelete?.();
          }}
          disabled={provisioned}
          title={provisioned ? t("workflows.messages.cannotDeleteProvisioned") : ""}
          data-testid="wf-menu-delete-button"
        />
      </DropdownMenu.Menu>
    </div>
  );
}
