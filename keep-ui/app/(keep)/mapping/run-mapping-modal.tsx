import { AlertDto } from "@/entities/alerts/model";
import { useApi } from "@/shared/lib/hooks/useApi";
import { showErrorToast } from "@/shared/ui";
import {
  Button,
  Dialog,
  DialogPanel,
  Select,
  SelectItem,
  Title,
} from "@tremor/react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useAlerts } from "utils/hooks/useAlerts";

interface Props {
  ruleId: number;
  isOpen: boolean;
  onClose: () => void;
}

export default function RunMappingModal({ ruleId, isOpen, onClose }: Props) {
  const { useLastAlerts } = useAlerts();
  const { data: alerts = [] } = useLastAlerts({
    cel: "",
    limit: 20,
    offset: 0,
  });
  const [selectedAlertId, setSelectedAlertId] = useState<string | undefined>();
  const [isLoading, setIsLoading] = useState(false);
  const api = useApi();
  const router = useRouter();

  const clearAndClose = () => {
    setSelectedAlertId(undefined);
    onClose();
  };

  const handleRun = async () => {
    if (!selectedAlertId) return;

    setIsLoading(true);
    try {
      const response = await api.post(
        `/mapping/${ruleId}/execute/${selectedAlertId}`
      );
      const { enrichment_event_id } = response;
      router.push(`/mapping/${ruleId}/executions/${enrichment_event_id}`);
      clearAndClose();
    } catch (error) {
      showErrorToast(error, "Failed to run mapping rule");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Dialog open={isOpen} onClose={clearAndClose} static={true}>
      <DialogPanel>
        <Title className="mb-1">Select alert to run mapping rule against</Title>

        {alerts.length > 0 ? (
          <Select
            value={selectedAlertId}
            onValueChange={setSelectedAlertId}
            placeholder="Select an alert..."
          >
            {alerts.map((alert) => (
              <SelectItem key={alert.event_id} value={alert.event_id}>
                <div className="flex flex-col">
                  <span className="font-medium">{alert.name}</span>
                  <span className="text-xs text-gray-500">
                    Fingerprint: {alert.fingerprint}
                  </span>
                </div>
              </SelectItem>
            ))}
          </Select>
        ) : (
          <div>No alerts found</div>
        )}

        <div className="flex justify-end gap-2 mt-4">
          <Button onClick={clearAndClose} color="orange" variant="secondary">
            Cancel
          </Button>
          <Button
            onClick={handleRun}
            color="orange"
            loading={isLoading}
            disabled={!selectedAlertId}
          >
            Run
          </Button>
        </div>
      </DialogPanel>
    </Dialog>
  );
}
