import React, { useState } from "react";
import Modal from "@/components/ui/Modal";
import { useAlerts } from "@/entities/alerts/model/useAlerts";
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
import { toast } from "react-toastify";

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

export const AlertErrorEventModal: React.FC<AlertErrorEventModalProps> = ({
  isOpen,
  onClose,
}) => {
  const { useErrorAlerts } = useAlerts();
  const { data: errorAlerts, dismissErrorAlerts, reprocessErrorAlerts } = useErrorAlerts();
  const [selectedAlertId, setSelectedAlertId] = useState<string>("");
  const [isDismissing, setIsDismissing] = useState<boolean>(false);
  const [isReprocessing, setIsReprocessing] = useState<boolean>(false);

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

  const handleReprocessSelected = async () => {
    if (selectedAlert) {
      setIsReprocessing(true);
      try {
        const result = await reprocessErrorAlerts(selectedAlert.id);
        if (result.success) {
          toast.success(
            `Reprocessed successfully! ${result.message || ""}`,
            { position: "top-right" }
          );

          // Handle navigation after successful reprocessing
          if (errorAlerts?.length === 1) {
            setSelectedAlertId("");
            onClose();
          } else if (parseInt(selectedAlertId, 10) === errorAlerts.length - 1) {
            setSelectedAlertId((parseInt(selectedAlertId, 10) - 1).toString());
          }
        } else {
          toast.error(`Reprocessing failed: ${result.message}`, {
            position: "top-right",
          });
        }
      } catch (error) {
        console.error("Failed to reprocess alert:", error);
        toast.error("Failed to reprocess alert", { position: "top-right" });
      } finally {
        setIsReprocessing(false);
      }
    }
  };

  const handleReprocessAll = async () => {
    setIsReprocessing(true);
    try {
      const result = await reprocessErrorAlerts();
      if (result.success) {
        toast.success(
          `Reprocessed ${result.successful || 0} alert(s) successfully!`,
          { position: "top-right" }
        );
        onClose();
      } else {
        toast.error(`Reprocessing failed: ${result.message}`, {
          position: "top-right",
        });
      }
    } catch (error) {
      console.error("Failed to reprocess alerts:", error);
      toast.error("Failed to reprocess alerts", { position: "top-right" });
    } finally {
      setIsReprocessing(false);
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
                    <div className="flex items-center">
                      <span className="mr-2">
                        {formatDate(alert.timestamp)}
                      </span>
                      <div className="mx-2">
                        <DynamicImageProviderIcon
                          providerType={alert.provider_type || "keep"}
                          width="16"
                          height="16"
                        />
                      </div>
                      <span>
                        Event from {alert.provider_type || "unknown provider"}
                      </span>
                    </div>
                  </SelectItem>
                ))}
              </Select>
            </div>
            <div className="flex space-x-2">
              <Button
                size="xs"
                color="blue"
                onClick={handleReprocessSelected}
                disabled={isReprocessing || !selectedAlert || isDismissing}
              >
                {isReprocessing ? "Reprocessing..." : "Reprocess current alert"}
              </Button>
              <Button
                size="xs"
                color="blue"
                variant="secondary"
                onClick={handleReprocessAll}
                disabled={isReprocessing || isDismissing}
              >
                {isReprocessing ? "Reprocessing..." : `Reprocess All (${errorAlerts.length})`}
              </Button>
              <Button
                size="xs"
                color="orange"
                onClick={handleDismissSelected}
                disabled={isDismissing || !selectedAlert || isReprocessing}
              >
                {isDismissing ? "Dismissing..." : "Dismiss current alert"}
              </Button>
              <Button
                size="xs"
                color="orange"
                variant="secondary"
                onClick={handleDismissAll}
                disabled={isDismissing || isReprocessing}
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
