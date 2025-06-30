import { type Provider } from "@/shared/api/providers";
import { type IncidentDto } from "@/entities/incidents/model";

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
    auth.host ||
    "";
}

/**
 * Get the ticket URL from an incident's enrichments for a specific provider
 */
export function getTicketViewUrl(incident: IncidentDto, provider: Provider): string {
  if (!incident.enrichments) return "";

  const urlKey = `${provider.type}_ticket_url`;
  return incident.enrichments[urlKey] || "";
}

/**
 * Construct a URL to create a new ticket in the provider's system
 */
export function getTicketCreateUrl(provider: Provider, description: string = "", title: string = ""): string {
  if (!provider.details?.authentication?.ticket_creation_url) {
    return "";
  }

  let createUrl = provider.details.authentication.ticket_creation_url;

  // TODO: might need to add other providers here
  if (provider.type === "servicenow") {
    createUrl = `${createUrl}/short_description=${title}&description=${description}`;
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

/**
 * Check if a provider can create tickets
 */
export function canCreateTickets(provider: Provider): boolean {
  // Check if provider has ticketing tag and ticket creation URL exists
  return provider.tags.includes("ticketing") && Boolean(provider.details?.authentication?.ticket_creation_url);
} 