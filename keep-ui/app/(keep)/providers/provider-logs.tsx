import { useI18n } from "@/i18n/hooks/useI18n";
import React from "react";
import { Card, Badge, Text, Button } from "@tremor/react";
import { useProviderLogs } from "@/utils/hooks/useProviderLogs";
import { ArrowPathIcon } from "@heroicons/react/24/outline";
import { KeepApiError } from "@/shared/api";
import { useConfig } from "@/utils/hooks/useConfig";
import { EmptyStateCard, ErrorComponent } from "@/shared/ui";
interface ProviderLogsProps {
  providerId: string;
}

const LOG_LEVEL_COLORS = {
  INFO: "blue",
  WARNING: "yellow",
  ERROR: "red",
  DEBUG: "gray",
  CRITICAL: "rose",
} as const;

const ProviderLogs: React.FC<ProviderLogsProps> = ({ providerId }) => {
  const { t } = useI18n();
  const { logs, isLoading, error, refresh } = useProviderLogs({ providerId });
  const { data: config } = useConfig();

  if (isLoading) {
    return <Text>{t("providers.logs.loading")}</Text>;
  }

  if (error) {
    if (error instanceof KeepApiError && error.statusCode === 404) {
      return (
        <div className="flex items-center">
          <EmptyStateCard
            title={t("providers.logs.notEnabledTitle")}
            description={t("providers.logs.notEnabledDescription")}
          >
            <Button
              color="orange"
              variant="primary"
              onClick={() =>
                window.open(
                  `${config?.KEEP_DOCS_URL || "https://docs.keephq.dev"}`,
                  "_blank"
                )
              }
            >
              {t("providers.logs.viewDocumentation")}
            </Button>
          </EmptyStateCard>
        </div>
      );
    }
    return (
      <div className="flex items-center">
        <ErrorComponent error={error} reset={() => refresh()} />
      </div>
    );
  }

  return (
    <div className="mt-4 space-y-4">
      <div className="flex justify-between items-center">
        <Text>{t("providers.logs.title")}</Text>
        <Button
          size="xs"
          variant="secondary"
          icon={ArrowPathIcon}
          onClick={() => refresh()}
        >
          {t("common.actions.refresh")}
        </Button>
      </div>

      <Card className="p-4">
        <div className="space-y-2 max-h-[500px] overflow-y-auto">
          {logs.map((log) => (
            <div key={log.id} className="flex items-start space-x-2">
              <Badge
                color={
                  LOG_LEVEL_COLORS[
                    log.log_level as keyof typeof LOG_LEVEL_COLORS
                  ] || "gray"
                }
              >
                {log.log_level}
              </Badge>
              <div className="flex-1">
                <Text>{log.log_message}</Text>
                {Object.keys(log.context).length > 0 && (
                  <pre className="mt-1 text-xs bg-gray-50 p-2 rounded">
                    {JSON.stringify(log.context, null, 2)}
                  </pre>
                )}
              </div>
              <Text className="text-xs text-gray-500">
                {new Date(log.timestamp).toLocaleString()}
              </Text>
            </div>
          ))}

          {logs.length === 0 && <Text>{t("providers.logs.noLogsFound")}</Text>}
        </div>
      </Card>
    </div>
  );
};

export default ProviderLogs;
