"use client";

import { useState, useMemo, useEffect } from "react";
import { Button, Text, Select, SelectItem } from "@tremor/react";
import Modal from "@/components/ui/Modal";
import { useFetchProviders } from "@/app/(keep)/providers/page.client";
import { type IncidentDto } from "@/entities/incidents/model";
import { type Provider } from "@/shared/api/providers";
import { getTicketCreateUrl } from "./ticketing-utils";

interface CreateTicketModalProps {
  incident: IncidentDto;
  isOpen: boolean;
  onClose: () => void;
}

export function CreateTicketModal({
  incident,
  isOpen,
  onClose,
}: CreateTicketModalProps) {
  const [selectedProviderId, setSelectedProviderId] = useState<string>("");
  const { installedProviders } = useFetchProviders();

  const ticketingProviders = useMemo(() => {
    return installedProviders.filter(
      (provider: Provider) => 
        provider.tags.includes("ticketing")
    );
  }, [installedProviders]);

  // Auto-select the provider if there's only one
  useEffect(() => {
    if (ticketingProviders.length === 1) {
      setSelectedProviderId(ticketingProviders[0].id);
    }
  }, [ticketingProviders]);

  // Get the selected provider
  const selectedProvider = useMemo(() => {
    return ticketingProviders.find(provider => provider.id === selectedProviderId);
  }, [ticketingProviders, selectedProviderId]);

  const handleCreateTicket = () => {
    if (!selectedProvider) return;
    
    const description = incident.user_summary || "";
    const title = incident.user_generated_name || "";
    
    const createUrl = getTicketCreateUrl(selectedProvider, description, title);
    
    if (createUrl) {
      window.open(createUrl);
      onClose();
    }
  };

  const handleCancel = () => {
    setSelectedProviderId("");
    onClose();
  };

  // Show loading state while providers are being fetched
  if (installedProviders.length === 0) {
    return (
      <Modal
        isOpen={isOpen}
        onClose={handleCancel}
        title="Create New Ticket"
        className="w-[500px]"
      >
        <div className="flex flex-col gap-4">
          <Text className="text-gray-500">
            Loading ticketing providers...
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

  // If no ticketing providers are available after loading
  if (ticketingProviders.length === 0) {
    return (
      <Modal
        isOpen={isOpen}
        onClose={handleCancel}
        title="Create New Ticket"
        className="w-[500px]"
      >
        <div className="flex flex-col gap-4">
          <Text className="text-red-500">
            No ticketing providers are configured. Please configure a ticketing provider first.
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
      title="Create New Ticket"
      className="w-[500px]"
    >
      <div className="flex flex-col gap-4">
        {/* Only show Select if there are multiple providers */}
        {ticketingProviders.length > 1 ? (
          <div>
            <Text className="mb-2">
              Select Ticketing Provider <span className="text-red-500">*</span>
            </Text>
            <Select
              placeholder="Select a ticketing provider"
              value={selectedProviderId}
              onValueChange={setSelectedProviderId}
            >
              {ticketingProviders.map((provider) => (
                <SelectItem key={provider.id} value={provider.id}>
                  {provider.display_name || provider.id}
                  {provider.details?.authentication && (
                    <span className="text-gray-500 ml-2">
                      ({provider.type})
                    </span>
                  )}
                </SelectItem>
              ))}
            </Select>
          </div>
        ) : null}

        {/* Show selected provider info */}
        {selectedProvider && (
          <div className="bg-gray-50 p-3 rounded-md">
            <Text className="text-sm font-medium mb-1">Selected Provider:</Text>
            <Text className="text-sm text-gray-600">
              {selectedProvider.display_name || selectedProvider.id}
            </Text>
            <Text className="text-sm text-gray-500 mt-1">
              You will be redirected to the {selectedProvider.display_name || selectedProvider.id} 
              
              ticketing provider with the following details:
            </Text>
            <Text className="text-sm text-gray-600 mt-1">
              <strong>Title:</strong> {incident.user_generated_name || "No title"}
            </Text>
            <Text className="text-sm text-gray-600">
              <strong>Description:</strong> {incident.user_summary || "No description"}
            </Text>
          </div>
        )}
        
        <div className="flex justify-end gap-2 pt-4">
          <Button
            variant="secondary"
            onClick={handleCancel}
          >
            Cancel
          </Button>
          <Button
            variant="primary"
            color="orange"
            onClick={handleCreateTicket}
            disabled={!selectedProviderId}
          >
            Create Ticket
          </Button>
        </div>
      </div>
    </Modal>
  );
} 