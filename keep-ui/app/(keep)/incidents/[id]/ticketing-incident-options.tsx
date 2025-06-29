"use client";

import { useState, useMemo } from "react";
import { Button } from "@tremor/react";
import { MdLink, MdModeEdit, MdOutlineBookmarkAdd, MdOutlineOpenInNew } from "react-icons/md";
import { type IncidentDto } from "@/entities/incidents/model";
import { LinkTicketModal } from "./link-ticket-modal";
import { CreateTicketModal } from "./create-ticket-modal";
import { useFetchProviders } from "@/app/(keep)/providers/page.client";
import { type Provider } from "@/shared/api/providers";
import { 
  findLinkedTicket, 
  getTicketViewUrl,
  type LinkedTicket 
} from "./ticketing-utils";

interface TicketingIncidentOptionsProps {
  incident: IncidentDto;
}

export function TicketingIncidentOptions({
  incident,
}: TicketingIncidentOptionsProps) {
  const [isLinkModalOpen, setIsLinkModalOpen] = useState(false);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const { installedProviders } = useFetchProviders();

  // Get ticketing providers from installed providers
  const ticketingProviders = useMemo(() => {
    return installedProviders.filter(
      (provider: Provider) => 
        provider.tags.includes("ticketing")
    );
  }, [installedProviders]);

  // Find the first linked ticket for this incident
  const linkedTicket = useMemo(() => {
    return findLinkedTicket(incident, ticketingProviders);
  }, [incident, ticketingProviders]);

  const linkIncidentToExistingTicket = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsLinkModalOpen(true);
  };

  const createNewTicket = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsCreateModalOpen(true);
  };

  const handleLinkSuccess = () => {
    // Trigger revalidation of incident data
    window.location.reload();
  };

  const openInProvider = () => {
    if (!linkedTicket) return;
    
    const providerUrl = getTicketViewUrl(linkedTicket);
    if (providerUrl) {
      window.open(providerUrl);
    }
  };

  return (
    <>
      {linkedTicket ? (
        <Button
          color="orange"
          size="xs"
          variant="secondary"
          className="!py-0.5 mr-2"
          icon={MdOutlineOpenInNew}
          onClick={openInProvider}
          disabled={!getTicketViewUrl(linkedTicket)}
        >
          Open in {linkedTicket.provider.display_name}
        </Button>
      ) : (
        <>
          <Button
            color="orange"
            size="xs"
            variant="secondary"
            className="!py-0.5 mr-2"
            icon={MdOutlineBookmarkAdd}
            onClick={createNewTicket}
          >
            Create New Ticket
          </Button>
          <Button
            color="orange"
            size="xs"
            variant="secondary"
            className="!py-0.5 mr-2"
            icon={MdLink}
            onClick={linkIncidentToExistingTicket}
          >
            Link to Existing Ticket
          </Button>
        </>
      )}

      <LinkTicketModal
        incident={incident}
        isOpen={isLinkModalOpen}
        onClose={() => setIsLinkModalOpen(false)}
        onSuccess={handleLinkSuccess}
      />

      <CreateTicketModal
        incident={incident}
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
      />
    </>
  );
} 