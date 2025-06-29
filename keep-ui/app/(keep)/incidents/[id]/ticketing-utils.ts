import { type Provider } from "@/shared/api/providers";

export interface LinkedTicket {
  provider: Provider;
  ticketId: string;
  key: string;
}

/**
 * Get the base URL from a provider's authentication details
 */
export function getProviderBaseUrl(provider: Provider): string {
  if (!provider?.details?.authentication) return "";
  
  const auth = provider.details.authentication;
  return auth.base_url || 
         auth.service_now_base_url || 
         auth.jira_base_url || 
         auth.zendesk_domain ||
         auth.freshdesk_domain ||
         "";
}

/**
 * Construct a URL to view a ticket in the provider's system
 */
export function getTicketViewUrl(linkedTicket: LinkedTicket): string {
  const { provider, ticketId } = linkedTicket;
  const baseUrl = getProviderBaseUrl(provider);
  
  if (!baseUrl) return "";
  
  switch (provider.type) {
    case "servicenow":
      return `${baseUrl}/now/nav/ui/classic/params/target/incident.do%3Fsys_id%3D${ticketId}`;
    case "jira":
      return `${baseUrl}/browse/${ticketId}`;
    case "zendesk":
      return `${baseUrl}/agent/tickets/${ticketId}`;
    case "freshdesk":
      return `${baseUrl}/helpdesk/tickets/${ticketId}`;
    default:
      // Generic fallback - try to construct a reasonable URL
      return `${baseUrl}/tickets/${ticketId}`;
  }
}

/**
 * Construct a URL to create a new ticket in the provider's system
 */
export function getTicketCreateUrl(provider: Provider, description: string = "", title: string = ""): string {
  const baseUrl = getProviderBaseUrl(provider);
  
  if (!baseUrl) return "";
  
  let createUrl = "";
  switch (provider.type) {
    case "servicenow":
      createUrl = `${baseUrl}/now/nav/ui/classic/params/target/incident.do%3Fsysparm_query%3D%26sysparm_stack%3Dincident_list.do%3Fsysparm_query%3Dactive%3Dtrue%26sysparm_first_row%3D1%26sysparm_view%3D`;
      break;
    case "jira":
      createUrl = `${baseUrl}/secure/CreateIssue.jspa`;
      break;
    case "zendesk":
      createUrl = `${baseUrl}/agent/filters/new`;
      break;
    case "freshdesk":
      createUrl = `${baseUrl}/helpdesk/tickets/new`;
      break;
    default:
      createUrl = `${baseUrl}/tickets/new`;
      break;
  }
  
  // Add description and title as query parameters if supported
  if (description || title) {
    const params = new URLSearchParams();
    if (description) params.append("description", description);
    if (title) params.append("title", title);
    
    const separator = createUrl.includes("?") ? "&" : "?";
    createUrl += separator + params.toString();
  }
  
  return createUrl;
}

/**
 * Find the first linked ticket for an incident from any ticketing provider
 */
export function findLinkedTicket(incident: any, ticketingProviders: Provider[]): LinkedTicket | null {
  if (!incident.enrichments) return null;
  
  // Look for any ticketing provider's ticket ID in enrichments
  for (const provider of ticketingProviders) {
    const ticketKey = `${provider.type}_ticket_id`;
    if (incident.enrichments[ticketKey]) {
      return {
        provider,
        ticketId: incident.enrichments[ticketKey],
        key: ticketKey
      };
    }
  }
  return null;
}

/**
 * Get the enrichment key for a specific provider
 */
export function getTicketEnrichmentKey(provider: Provider): string {
  return `${provider.type}_ticket_id`;
} 