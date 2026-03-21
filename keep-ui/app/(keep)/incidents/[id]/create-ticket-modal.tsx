"use client";

import { useState, useMemo, useEffect } from "react";
import { Button, Text, Select, SelectItem, TextInput, Textarea } from "@tremor/react";
import Modal from "@/components/ui/Modal";
import { DynamicImageProviderIcon } from "@/components/ui";
import { useFetchProviders } from "@/app/(keep)/providers/page.client";
import { type IncidentDto } from "@/entities/incidents/model";
import { type Provider } from "@/shared/api/providers";
import { getProviderBaseUrl, getTicketCreateUrl, canCreateTickets } from "@/entities/incidents/lib/ticketing-utils";
import { useTranslations } from "next-intl";interface CreateTicketModalProps {
  incident: IncidentDto;
  isOpen: boolean;
  onClose: () => void;
}

export function CreateTicketModal({
  incident,
  isOpen,
  onClose,
}: CreateTicketModalProps) {
  const t = useTranslations("incidents");
  const [selectedProviderId, setSelectedProviderId] = useState<string>("");
  const [ticketTitle, setTicketTitle] = useState<string>("");
  const [ticketDescription, setTicketDescription] = useState<string>("");
  const { installedProviders, isLoading: isLoadingProviders } = useFetchProviders();

  // Initialize title and description when modal opens or incident changes
  useEffect(() => {
    setTicketTitle(incident.user_generated_name || "");
    setTicketDescription((incident.user_summary || "").replace(/<[^>]*>/g, ''));
  }, [incident, isOpen]);

  const ticketingProviders = useMemo(() => {
    return installedProviders.filter(canCreateTickets);
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

    const createUrl = getTicketCreateUrl(selectedProvider, ticketDescription, ticketTitle);

    if (createUrl) {
      window.open(createUrl);
      onClose();
    }
  };

  const handleCancel = () => {
    setSelectedProviderId("");
    setTicketTitle("");
    setTicketDescription("");
    onClose();
  };

  // Show loading state while providers are being fetched
  if (isLoadingProviders) {
    return (
      <Modal
        isOpen={isOpen}
        onClose={handleCancel}
        title={t("actions.createTicket")}
        className="w-[450px]"
      >
        <div className="flex flex-col gap-4">
          <Text className="text-gray-500">
            {t("messages.loadingProviders")}
          </Text>
          <div className="flex justify-end">
            <Button variant="secondary" onClick={handleCancel}>
              {t("common:actions.close", { ns: "common" })}
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
        title={t("actions.createTicket")}
        className="w-[450px]"
      >
        <div className="flex flex-col gap-4">
          <Text className="text-red-500">
            {t("messages.noProvidersConfigured")}
          </Text>
          <div className="flex justify-end">
            <Button variant="secondary" onClick={handleCancel}>
              {t("common:actions.close", { ns: "common" })}
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
      title={t("actions.createTicket")}
      className="w-[450px]"
    >
      <div className="flex flex-col gap-2">
        {/* Only show Select if there are multiple providers */}
        {ticketingProviders.length > 1 ? (
          <div>
            <Text className="mb-2">
              {t("labels.selectTicketingProvider")} <span className="text-red-500">*</span>
            </Text>
            <Select
              placeholder={t("labels.selectProvider")}
              value={selectedProviderId}
              onValueChange={setSelectedProviderId}
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
        ) : null}

        {/* Ticket Title Input */}
        <div>
          <Text className="mb-2">
            {t("labels.ticketTitle")} <span className="text-red-500">*</span>
          </Text>
          <TextInput
            placeholder={t("labels.enterTicketTitle")}
            value={ticketTitle}
            onChange={(e) => setTicketTitle(e.target.value)}
          />
        </div>

        {/* Ticket Description Input */}
        <div>
          <Text className="mb-2">
            {t("labels.ticketDescription")}
          </Text>
          <Textarea
            placeholder={t("labels.enterTicketDescription")}
            value={ticketDescription}
            onChange={(e) => setTicketDescription(e.target.value.replace(/<[^>]*>/g, ''))}
            rows={4}
          />
        </div>

        {/* Show selected provider info */}
        {selectedProvider && (
          <>
            <Text className="text-sm font-medium mb-1">{t("labels.selectedProvider")}</Text>

            <div className="bg-gray-50 p-3 rounded-md space-y-2">
              <div className="flex items-center gap-3">
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

              </div>
              <Text className="text-xsm text-gray-500 ml-2 break-all">
                  {getProviderBaseUrl(selectedProvider)}
                </Text>
            </div>
            <div className="mt-1 p-2 bg-blue-50 border border-blue-200 rounded-md">
              <Text className="text-sm text-blue-700">
                {t("messages.ticketNote")}
              </Text>
            </div>
            <Text className="text-sm text-orange-500 mt-1">
              {t("messages.redirectToProvider", { provider: selectedProvider.display_name || selectedProvider.id })}
            </Text>
          </>
        )}


        <div className="flex justify-end gap-2 pt-2">
          <Button
            variant="secondary"
            onClick={handleCancel}
          >
            {t("common:actions.cancel", { ns: "common" })}
          </Button>
          <Button
            variant="primary"
            color="orange"
            onClick={handleCreateTicket}
            disabled={!selectedProviderId || !ticketTitle.trim()}
          >
            {t("actions.createTicket")}
          </Button>
        </div>
      </div>
    </Modal>
  );
} 