"use client";

import { useState, useMemo } from "react";
import { Button, Text, Select, SelectItem } from "@tremor/react";
import Modal from "@/components/ui/Modal";
import { TextInput } from "@/components/ui";
import { useApi } from "@/shared/lib/hooks/useApi";
import { useFetchProviders } from "@/app/(keep)/providers/page.client";
import { showSuccessToast, showErrorToast } from "@/shared/ui";
import { type IncidentDto } from "@/entities/incidents/model";
import { type Provider } from "@/shared/api/providers";

interface LinkServiceNowTicketModalProps {
  incident: IncidentDto;
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

export function LinkServiceNowTicketModal({
  incident,
  isOpen,
  onClose,
  onSuccess,
}: LinkServiceNowTicketModalProps) {
  const [ticketId, setTicketId] = useState("");
  const [selectedProviderId, setSelectedProviderId] = useState<string>("");
  const [isLoading, setIsLoading] = useState(false);
  const api = useApi();
  const { installedProviders } = useFetchProviders();

  const serviceNowProviders = useMemo(() => {
    return installedProviders.filter(
      (provider: Provider) => 
        provider.type === "servicenow"
    );
  }, [installedProviders]);

  // Get the selected provider
  const selectedProvider = useMemo(() => {
    return serviceNowProviders.find(provider => provider.id === selectedProviderId);
  }, [serviceNowProviders, selectedProviderId]);

  // Get the base URL from the selected provider
  const serviceNowBaseUrl = useMemo(() => {
    if (!selectedProvider?.details?.authentication) return "";
    return selectedProvider.details.authentication.service_now_base_url || "";
  }, [selectedProvider]);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    
    if (!ticketId.trim()) {
      showErrorToast(new Error("Please enter a ServiceNow ticket ID"));
      return;
    }

    if (serviceNowProviders.length > 1 && !selectedProviderId) {
      showErrorToast(new Error("Please select a ServiceNow provider"));
      return;
    }

    setIsLoading(true);
    
    try {
      // Enrich the incident with the ServiceNow ticket ID
      await api.post(`/incidents/${incident.id}/enrich`, {
        enrichments: {
          servicenow_ticket_id: ticketId.trim(),
        },
      });

      showSuccessToast("Successfully linked incident to ServiceNow ticket");
      setTicketId("");
      setSelectedProviderId("");
      onSuccess?.();
      onClose();
    } catch (error) {
      showErrorToast(error, "Failed to link incident to ServiceNow ticket");
    } finally {
      setIsLoading(false);
    }
  };

  const handleCancel = () => {
    setTicketId("");
    setSelectedProviderId("");
    onClose();
  };

  // Show loading state while providers are being fetched
  if (installedProviders.length === 0) {
    return (
      <Modal
        isOpen={isOpen}
        onClose={handleCancel}
        title="Link to Existing ServiceNow Ticket"
        className="w-[500px]"
      >
        <div className="flex flex-col gap-4">
          <Text className="text-gray-500">
            Loading ServiceNow providers...
          </Text>
          <div className="flex justify-end">
            <Button variant="secondary" onClick={handleCancel}>
              Close
            </Button>
          </div>
        </div>
      </Modal>
    );
  }

  // If no ServiceNow providers are available after loading
  if (serviceNowProviders.length === 0) {
    return (
      <Modal
        isOpen={isOpen}
        onClose={handleCancel}
        title="Link to Existing ServiceNow Ticket"
        className="w-[500px]"
      >
        <div className="flex flex-col gap-4">
          <Text className="text-red-500">
            No ServiceNow providers are configured. Please configure a ServiceNow provider first.
          </Text>
          <div className="flex justify-end">
            <Button variant="secondary" onClick={handleCancel}>
              Close
            </Button>
          </div>
        </div>
      </Modal>
    );
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleCancel}
      title="Link to Existing ServiceNow Ticket"
      className="w-[500px]"
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        {/* Provider Selection (only show if there are multiple Ticketing providers) */}
        {serviceNowProviders.length > 1 && (
          <div>
            <Text className="mb-2">
              ServiceNow Provider <span className="text-red-500">*</span>
            </Text>
            <Select
              placeholder="Select a ServiceNow provider"
              value={selectedProviderId}
              onValueChange={setSelectedProviderId}
              disabled={isLoading}
            >
              {serviceNowProviders.map((provider) => (
                <SelectItem key={provider.id} value={provider.id}>
                  {provider.display_name || provider.id}
                  {provider.details?.authentication?.service_now_base_url && (
                    <span className="text-gray-500 ml-2">
                      ({provider.details.authentication.service_now_base_url})
                    </span>
                  )}
                </SelectItem>
              ))}
            </Select>
          </div>
        )}

        {/* Show selected provider info if single provider or provider is selected */}
        {(serviceNowProviders.length === 1 || selectedProviderId) && (
          <div className="bg-gray-50 p-3 rounded-md">
            <Text className="text-sm font-medium mb-1">Selected Provider:</Text>
            <Text className="text-sm text-gray-600">
              {selectedProvider?.display_name || selectedProvider?.id}
            </Text>
            {serviceNowBaseUrl && (
              <Text className="text-sm text-gray-600">
                Base URL: {serviceNowBaseUrl}
              </Text>
            )}
          </div>
        )}

        <div>
          <Text className="mb-2">
            ServiceNow Ticket ID <span className="text-red-500">*</span>
          </Text>
          <TextInput
            placeholder="Enter ServiceNow ticket ID (e.g., INC0012345)"
            value={ticketId}
            onChange={(e) => setTicketId(e.target.value)}
            required
            disabled={isLoading}
          />
        </div>
        
        <div className="flex justify-end gap-2 pt-4">
          <Button
            variant="secondary"
            onClick={handleCancel}
            disabled={isLoading}
          >
            Cancel
          </Button>
          <Button
            variant="primary"
            color="orange"
            type="submit"
            disabled={isLoading || !ticketId.trim() || (serviceNowProviders.length > 1 && !selectedProviderId)}
          >
            {isLoading ? "Linking..." : "Link Ticket"}
          </Button>
        </div>
      </form>
    </Modal>
  );
} 