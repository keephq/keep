"use client";

import { useState, useMemo, useEffect } from "react";
import { Button, Text, Select, SelectItem } from "@tremor/react";
import Modal from "@/components/ui/Modal";
import { TextInput } from "@/components/ui";
import { DynamicImageProviderIcon } from "@/components/ui";
import { useApi } from "@/shared/lib/hooks/useApi";
import { useFetchProviders } from "@/app/(keep)/providers/page.client";
import { showSuccessToast, showErrorToast } from "@/shared/ui";
import { type IncidentDto } from "@/entities/incidents/model";
import { type Provider } from "@/shared/api/providers";
import { getProviderBaseUrl, getTicketEnrichmentKey } from "./ticketing-utils";

interface LinkTicketModalProps {
  incident: IncidentDto;
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

export function LinkTicketModal({
  incident,
  isOpen,
  onClose,
  onSuccess,
}: LinkTicketModalProps) {
  const [ticketId, setTicketId] = useState("");
  const [ticketUrl, setTicketUrl] = useState("");
  const [selectedProviderId, setSelectedProviderId] = useState<string>("");
  const [isLoading, setIsLoading] = useState(false);
  const api = useApi();
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

  // Get the base URL from the selected provider (if available)
  const providerBaseUrl = useMemo(() => {
    if (!selectedProvider) return "";
    return getProviderBaseUrl(selectedProvider);
  }, [selectedProvider]);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    if (!ticketUrl.trim()) {
      showErrorToast(new Error("Please enter a ticket URL"));
      return;
    }

    if (ticketingProviders.length > 1 && !selectedProviderId) {
      showErrorToast(new Error("Please select a ticketing provider"));
      return;
    }

    setIsLoading(true);

    try {
      const enrichments: Record<string, string> = {};

      // Add ticket ID if provided
      if (ticketId.trim()) {
        const enrichmentKey = selectedProvider ?
          getTicketEnrichmentKey(selectedProvider) :
          'ticketing_ticket_id';
        enrichments[enrichmentKey] = ticketId.trim();
      }

      // Add ticket URL (required)
      const urlEnrichmentKey = selectedProvider ?
        `${selectedProvider.type}_ticket_url` :
        'ticketing_ticket_url';
      enrichments[urlEnrichmentKey] = ticketUrl.trim();

      await api.post(`/incidents/${incident.id}/enrich`, {
        enrichments,
      });

      showSuccessToast("Successfully linked incident to ticket");
      setTicketId("");
      setTicketUrl("");
      setSelectedProviderId("");
      onSuccess?.();
      onClose();
    } catch (error) {
      showErrorToast(error, "Failed to link incident to ticket");
    } finally {
      setIsLoading(false);
    }
  };

  const handleCancel = () => {
    setTicketId("");
    setTicketUrl("");
    setSelectedProviderId("");
    onClose();
  };

  // Show loading state while providers are being fetched
  if (installedProviders.length === 0) {
    return (
      <Modal
        isOpen={isOpen}
        onClose={handleCancel}
        title="Link to Existing Ticket"
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
        title="Link to Existing Ticket"
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
      title="Link to Existing Ticket"
      className="w-[500px]"
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        {/* Provider Selection (only show if there are multiple ticketing providers) */}
        {ticketingProviders.length > 1 && (
          <div>
            <Text className="mb-2">
              Ticketing Provider <span className="text-red-500">*</span>
            </Text>
            <Select
              placeholder="Select a ticketing provider"
              value={selectedProviderId}
              onValueChange={setSelectedProviderId}
              disabled={isLoading}
            >
              {ticketingProviders.map((provider) => (
                <SelectItem key={provider.id} value={provider.id}>
                  <div className="flex items-center gap-2">
                    <DynamicImageProviderIcon
                      src={`/icons/${provider.type}-icon.png`}
                      width={20}
                      height={20}
                      alt={provider.type}
                      providerType={provider.type}
                    />
                    <span>
                      {provider.display_name || provider.id}
                    </span>
                    <span>
                      {provider.details?.authentication && (
                        <span className="text-gray-500 ml-2">
                          ({getProviderBaseUrl(provider)})
                        </span>
                      )}
                    </span>
                  </div>
                </SelectItem>
              ))}
            </Select>
          </div>
        )}

        {/* Show selected provider info if single provider or provider is selected */}
        {(ticketingProviders.length === 1 || selectedProviderId) && (
          <>
            <Text className="text-sm font-medium mb-1">Selected Provider</Text>
            <div className="bg-gray-50 p-3 rounded-md space-y-2">
              <div className="flex items-center gap-3">
                {selectedProvider && (
                  <>
                    <DynamicImageProviderIcon
                      src={`/icons/${selectedProvider.type}-icon.png`}
                      width={30}
                      height={30}
                      alt={selectedProvider.type}
                      providerType={selectedProvider.type}
                    />
                    <Text className="text-base text-gray-600">
                      {selectedProvider.display_name || selectedProvider.id}
                    </Text>
                  </>
                )}
              </div>
              <Text className="text-xsm text-gray-500 ml-2 break-all">
                {selectedProvider ? getProviderBaseUrl(selectedProvider) : ""}
              </Text>
            </div>
          </>
        )}

        <div>
          <Text className="mb-2">
            Ticket ID <span className="text-gray-500">(optional)</span>
          </Text>
          <TextInput
            placeholder={`Enter ${selectedProvider?.display_name || 'ticketing'} ticket ID`}
            value={ticketId}
            onChange={(e) => setTicketId(e.target.value)}
            disabled={isLoading}
          />
        </div>

        <div>
          <Text className="mb-2">
            Ticket URL <span className="text-red-500">*</span>
          </Text>
          <TextInput
            placeholder="Enter the full URL to the ticket (e.g., https://company.atlassian.net/browse/PROJ-123)"
            value={ticketUrl}
            onChange={(e) => setTicketUrl(e.target.value)}
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
            disabled={isLoading || !ticketUrl.trim() || (ticketingProviders.length > 1 && !selectedProviderId)}
          >
            {isLoading ? "Linking..." : "Link Ticket"}
          </Button>
        </div>
      </form>
    </Modal>
  );
} 