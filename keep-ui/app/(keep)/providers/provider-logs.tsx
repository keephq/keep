import React from "react";
import { Card, Title, Badge, Text, Button } from "@tremor/react";
import { useProviderLogs, ProviderLog } from "@/utils/hooks/useProviderLogs";
import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import { ArrowPathIcon } from "@heroicons/react/24/outline";

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
  const { logs, isLoading, error, refresh } = useProviderLogs({ providerId });

  if (isLoading) {
    return <Text>Loading logs...</Text>;
  }

  if (error) {
    return (
      <div className="flex items-center">
        <EmptyStateCard
          title="Provider Logs Not Enabled"
          description="Provider logs need to be enabled on the backend. Please check the documentation for instructions on how to enable provider logs."
          buttonText="View Documentation"
          onClick={() => window.open("https://docs.keephq.dev", "_blank")}
        />
      </div>
    );
  }

  return (
    <div className="mt-4 space-y-4">
      <div className="flex justify-between items-center">
        <Text>Provider Logs</Text>
        <Button
          size="xs"
          variant="secondary"
          icon={ArrowPathIcon}
          onClick={() => refresh()}
        >
          Refresh
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

          {logs.length === 0 && <Text>No logs found</Text>}
        </div>
      </Card>
    </div>
  );
};

export default ProviderLogs;
