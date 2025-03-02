import { Switch } from "@tremor/react";
import { useLocalStorage } from "utils/hooks/useLocalStorage";

interface ActionTraySelectionProps {
  onClose: () => void;
}

export function ActionTraySelection({ onClose }: ActionTraySelectionProps) {
  const [showActionsOnHover, setShowActionsOnHover] = useLocalStorage(
    "alert-action-tray-hover",
    true
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex flex-col">
          <span className="text-sm font-medium text-gray-900">
            Show actions on hover
          </span>
          <span className="text-sm text-gray-500">
            Toggle between showing actions always or only on row hover
          </span>
        </div>
        <Switch
          checked={showActionsOnHover}
          onChange={setShowActionsOnHover}
          color="orange"
        />
      </div>
    </div>
  );
}
