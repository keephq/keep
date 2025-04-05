import { Tooltip } from "@/shared/ui";
import { LockClosedIcon } from "@radix-ui/react-icons";
import { Icon } from "@tremor/react";

export function WorkflowPermissionsBadge({
  permissions,
  showTooltip = true,
}: {
  permissions: string[];
  showTooltip?: boolean;
}) {
  const badge = (
    <div className="border bg-white border-gray-500 p-0.5 pr-2.5 pl-1.5 text-black placeholder-opacity-100 text-xs rounded-3xl font-medium flex items-center gap-1 capitalizehover:bg-white hover:border-gray-500 cursor-default hover:bg-gray-100 w-28">
      <Icon color={"black"} className="size-5" icon={LockClosedIcon} />
      <span className="text-xs truncate">Requires Permissions</span>
    </div>
  );

  if (!showTooltip) {
    return badge;
  }

  return (
    <Tooltip content={permissions.join(", ")} asChild>
      {badge}
    </Tooltip>
  );
}
