"use client";

import { useState, useMemo } from "react";
import { Button } from "@tremor/react";
import { MdLink, MdModeEdit, MdOutlineBookmarkAdd, MdOutlineOpenInNew } from "react-icons/md";
import { type IncidentDto } from "@/entities/incidents/model";
import { LinkServiceNowTicketModal } from "./link-servicenow-ticket-modal";
import { useFetchProviders } from "@/app/(keep)/providers/page.client";
import { type Provider } from "@/shared/api/providers";

interface ServiceNowIncidentOptionsProps {
  incident: IncidentDto;
}

export function ServiceNowIncidentOptions({
  incident,
}: ServiceNowIncidentOptionsProps) {
  const [isLinkModalOpen, setIsLinkModalOpen] = useState(false);
  const { installedProviders } = useFetchProviders();

  // Get ServiceNow providers from installed providers
  const serviceNowProviders = useMemo(() => {
    return installedProviders.filter(
      (provider: Provider) => 
        provider.type === "servicenow" 
    );
  }, [installedProviders]);

  // Get the first ServiceNow provider's base URL (for the "Open in ServiceNow" button)
  const serviceNowBaseUrl = useMemo(() => {
    if (serviceNowProviders.length === 0) return "";
    const firstProvider = serviceNowProviders[0];
    return firstProvider.details?.authentication?.service_now_base_url || "";
  }, [serviceNowProviders]);

  const linkIncidentToExistingTicket = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsLinkModalOpen(true);
  };

  const handleLinkSuccess = () => {
    // Trigger revalidation of incident data
    window.location.reload();
  };

  const openInServiceNow = () => {
    if (!serviceNowBaseUrl || !incident.enrichments?.servicenow_ticket_id) {
      return;
    }
    
    // Construct the ServiceNow incident URL
    const ticketId = incident.enrichments.servicenow_ticket_id;
    const serviceNowUrl = `${serviceNowBaseUrl}/now/nav/ui/classic/params/target/incident.do%3Fsys_id%3D${ticketId}`;
    window.open(serviceNowUrl);
  };

  return (
    <>
      {incident.enrichments?.servicenow_ticket_id ? (
        <Button
          color="orange"
          size="xs"
          variant="secondary"
          className="!py-0.5 mr-2"
          icon={MdOutlineOpenInNew}
          onClick={openInServiceNow}
          disabled={!serviceNowBaseUrl}
        >
          Open incident in ServiceNow
        </Button>
      ) : (
        <>
          <Button
            color="orange"
            size="xs"
            variant="secondary"
            className="!py-0.5 mr-2"
            icon={MdOutlineBookmarkAdd}
            onClick={(e: React.MouseEvent) => {
              e.preventDefault();
              e.stopPropagation();
              console.log(incident);
              window.open(`https://localhost:3000/?description=${incident.user_summary}&short_description=${incident.user_generated_name}`);
            }}
          >
            Create New ServiceNow Ticket
          </Button>
          <Button
            color="orange"
            size="xs"
            variant="secondary"
            className="!py-0.5 mr-2"
            icon={MdLink}
            onClick={linkIncidentToExistingTicket}
          >
            Link to a ServiceNow Ticket
          </Button>
        </>
      )}

      <LinkServiceNowTicketModal
        incident={incident}
        isOpen={isLinkModalOpen}
        onClose={() => setIsLinkModalOpen(false)}
        onSuccess={handleLinkSuccess}
      />
    </>
  );
} 