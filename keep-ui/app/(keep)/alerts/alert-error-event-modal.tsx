import React, { useState } from "react";
import Modal from "@/components/ui/Modal";
import { useAlerts } from "utils/hooks/useAlerts";
import {
  Card,
  Text,
  Title,
  Subtitle,
  Select,
  SelectItem,
  Badge,
  Callout,
  Button,
} from "@tremor/react";
import { DynamicImageProviderIcon } from "@/components/ui/DynamicProviderIcon";

interface ErrorAlert {
  id: string;
  provider_type?: string;
  event: Record<string, any>;
  error_message: string;
  timestamp: string;
}

interface AlertErrorEventModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const AlertErrorEventModal: React.FC<AlertErrorEventModalProps> = ({
  isOpen,
  onClose,
}) => {
  const { useErrorAlerts } = useAlerts();
  const { data: errorAlerts, dismissErrorAlerts } = useErrorAlerts();
  const [selectedAlertId, setSelectedAlertId] = useState<string>("");
  const [isDismissing, setIsDismissing] = useState<boolean>(false);

  // Set the first alert as selected when data loads or changes
  React.useEffect(() => {
    if (errorAlerts?.length > 0 && !selectedAlertId) {
      setSelectedAlertId("0");
    } else if (errorAlerts?.length === 0) {
      setSelectedAlertId("");
    }
  }, [errorAlerts, selectedAlertId]);

  const formatDate = (dateString: string) => {
    try {
      const date = new Date(dateString);
      return date.toLocaleString();
    } catch (error) {
      return dateString;
    }
  };

  const selectedAlert =
    errorAlerts?.[parseInt(selectedAlertId, 10)] || errorAlerts?.[0];

  const handleAlertChange = (value: string) => {
    setSelectedAlertId(value);
  };

  const handleDismissSelected = async () => {
    if (selectedAlert) {
      setIsDismissing(true);
      try {
        await dismissErrorAlerts(selectedAlert.id);
        if (errorAlerts?.length === 1) {
          setSelectedAlertId("");
          // Close the modal if it was the only alert
          onClose();
        } else if (parseInt(selectedAlertId, 10) === errorAlerts.length - 1) {
          // If it's the last item, select the previous one
          setSelectedAlertId((parseInt(selectedAlertId, 10) - 1).toString());
        }
      } catch (error) {
        console.error("Failed to dismiss alert:", error);
      } finally {
        setIsDismissing(false);
      }
    }
  };

  const handleDismissAll = async () => {
    setIsDismissing(true);
    try {
      await dismissErrorAlerts(); // No ID means dismiss all
      setSelectedAlertId("");
      // Close the modal after successfully dismissing all alerts
      onClose();
    } catch (error) {
      console.error("Failed to dismiss all alerts:", error);
    } finally {
      setIsDismissing(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      className="w-[80%] max-w-screen-2xl max-h-[80vh] transform overflow-auto ring-tremor bg-white p-6 text-left align-middle shadow-tremor transition-all rounded-xl"
    >
      <div className="flex justify-between items-center mb-4">
        <Title>Events failed to process ({errorAlerts?.length || 0})</Title>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-500">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>

      {errorAlerts?.length ? (
        <>
          <div className="mb-4 flex justify-between items-center">
            <div className="flex-grow mr-4">
              <Select
                value={selectedAlertId}
                onValueChange={handleAlertChange}
                placeholder="Select an error alert"
              >
                {errorAlerts.map((alert: ErrorAlert, index: number) => (
                  <SelectItem key={index} value={index.toString()}>
                    {formatDate(alert.timestamp)} - Event from{" "}
                    {alert.provider_type || "unknown provider"}
                  </SelectItem>
                ))}
              </Select>
            </div>
            <div className="flex space-x-2">
              <Button
                size="xs"
                color="orange"
                onClick={handleDismissSelected}
                disabled={isDismissing || !selectedAlert}
              >
                {isDismissing ? "Dismissing..." : "Dismiss current alert"}
              </Button>
              <Button
                size="xs"
                color="orange"
                variant="secondary"
                onClick={handleDismissAll}
                disabled={isDismissing}
              >
                {isDismissing ? "Dismissing..." : "Dismiss All"}
              </Button>
            </div>
          </div>

          {selectedAlert && (
            <Card className="p-4">
              <div className="flex items-start mb-4">
                {selectedAlert.provider_type && (
                  <div className="mr-2 mt-1">
                    <DynamicImageProviderIcon
                      providerType={selectedAlert.provider_type || "keep"}
                      width="16"
                      height="16"
                    />
                  </div>
                )}
                <Title>
                  Error parsing event{" "}
                  {selectedAlert.provider_type
                    ? `from ${selectedAlert.provider_type}`
                    : ""}
                </Title>
              </div>

              <div className="mb-4">
                <Subtitle>Timestamp</Subtitle>
                <Badge color="orange">
                  {formatDate(selectedAlert.timestamp)}
                </Badge>
              </div>

              <div>
                <Subtitle>Raw Event Data</Subtitle>
                <pre className="mt-1 p-3 bg-gray-100 rounded-md text-xs overflow-x-auto whitespace-pre-wrap">
                  {JSON.stringify(selectedAlert.event, null, 2)}
                </pre>
              </div>

              <div className="mb-4 mt-4">
                <Subtitle>Stack Trace</Subtitle>
                <pre className="mt-1 p-3 bg-gray-100 rounded-md text-xs overflow-x-auto whitespace-pre-wrap">
                  {selectedAlert.error_message}
                </pre>
              </div>
            </Card>
          )}
        </>
      ) : (
        <Text className="text-center py-8">No error alerts found</Text>
      )}
    </Modal>
  );
};

export default AlertErrorEventModal;
