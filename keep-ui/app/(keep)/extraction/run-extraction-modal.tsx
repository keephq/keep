import { useI18n } from "@/i18n/hooks/useI18n";
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
import { useAlerts } from "@/entities/alerts/model/useAlerts";

interface Props {
  ruleId: number;
  isOpen: boolean;
  onClose: () => void;
}

export default function RunExtractionModal({ ruleId, isOpen, onClose }: Props) {
  const { t } = useI18n();
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
        `/extraction/${ruleId}/execute/${selectedAlertId}`
      );
      const { enrichment_event_id } = response;
      router.push(`/extraction/${ruleId}/executions/${enrichment_event_id}`);
      clearAndClose();
    } catch (error) {
      showErrorToast(error, t("extraction.runFailed"));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Dialog open={isOpen} onClose={clearAndClose} static={true}>
      <DialogPanel>
        <Title className="mb-1">
          {t("extraction.selectAlertTitle")}
        </Title>

        {alerts.length > 0 ? (
          <Select
            value={selectedAlertId}
            onValueChange={setSelectedAlertId}
            placeholder={t("extraction.selectAlertPlaceholder")}
          >
            {alerts.map((alert) => (
              <SelectItem key={alert.event_id} value={alert.event_id}>
                <div className="flex flex-col">
                  <span className="font-medium">{alert.name}</span>
                  <span className="text-xs text-gray-500">
                    {t("extraction.fingerprint")}: {alert.fingerprint}
                  </span>
                </div>
              </SelectItem>
            ))}
          </Select>
        ) : (
          <div>{t("extraction.noAlerts")}</div>
        )}

        <div className="flex justify-end gap-2 mt-4">
          <Button onClick={clearAndClose} color="orange" variant="secondary">
            {t("common.actions.cancel")}
          </Button>
          <Button
            onClick={handleRun}
            color="orange"
            loading={isLoading}
            disabled={!selectedAlertId}
          >
            {t("common.actions.run")}
          </Button>
        </div>
      </DialogPanel>
    </Dialog>
  );
}
