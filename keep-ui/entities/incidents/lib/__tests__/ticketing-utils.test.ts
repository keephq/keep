import { 
  getProviderBaseUrl, 
  getTicketViewUrl, 
  getTicketCreateUrl, 
  findLinkedTicket,
  getTicketEnrichmentKey,
  type LinkedTicket 
} from "../ticketing-utils";
import { type Provider } from "@/shared/api/providers";
import { Status, Severity, type IncidentDto } from "@/entities/incidents/model/models";

// Mock provider data for testing
const mockServiceNowProvider: Provider = {
  id: "servicenow",
  type: "servicenow",
  display_name: "ServiceNow",
  tags: ["ticketing"],
  config: {},
  installed: true,
  linked: true,
  last_alert_received: "",
  details: {
    authentication: {
      service_now_base_url: "https://company.service-now.com",
      ticket_creation_url: "https://company.service-now.com/now/sow/record/incident/-1/params"
    }
  },
  can_query: false,
  can_notify: true,
  validatedScopes: {},
  pulling_available: false,
  pulling_enabled: true,
  categories: ["Ticketing"],
  coming_soon: false,
  health: false,
};

const mockJiraProvider: Provider = {
  id: "jira",
  type: "jira",
  display_name: "Jira",
  tags: ["ticketing"],
  config: {},
  installed: true,
  linked: true,
  last_alert_received: "",
  details: {
    authentication: {
      jira_base_url: "https://company.atlassian.net",
      ticket_creation_url: "https://company.atlassian.net/secure/CreateIssue.jspa"
    }
  },
  can_query: false,
  can_notify: true,
  validatedScopes: {},
  pulling_available: false,
  pulling_enabled: true,
  categories: ["Ticketing"],
  coming_soon: false,
  health: false,
};

const mockZendeskProvider: Provider = {
  id: "zendesk",
  type: "zendesk",
  display_name: "Zendesk",
  tags: ["ticketing"],
  config: {},
  installed: true,
  linked: true,
  last_alert_received: "",
  details: {
    authentication: {
      host: "https://company.zendesk.com",
      ticket_creation_url: "https://company.zendesk.com/agent/filters/new"
    }
  },
  can_query: false,
  can_notify: true,
  validatedScopes: {},
  pulling_available: false,
  pulling_enabled: true,
  categories: ["Ticketing"],
  coming_soon: false,
  health: false,
};

// Mock incident data for testing
const createMockIncident = (enrichments: Record<string, any> = {}): IncidentDto => ({
  id: "test-incident-id",
  user_generated_name: "Test Incident",
  ai_generated_name: "Test Incident",
  user_summary: "Test summary",
  generated_summary: "Test generated summary",
  assignee: "test-assignee",
  status: Status.Firing,
  severity: Severity.High,
  alerts_count: 1,
  alert_sources: ["test-source"],
  services: ["test-service"],
  creation_time: new Date(),
  is_candidate: false,
  rule_fingerprint: "test-fingerprint",
  same_incident_in_the_past_id: "",
  following_incidents_ids: [],
  merged_into_incident_id: "",
  merged_by: "",
  merged_at: new Date(),
  fingerprint: "test-fingerprint",
  enrichments,
  resolve_on: "all_resolved",
});

describe("ticketing-utils", () => {
  describe("getProviderBaseUrl", () => {
    it("should extract ServiceNow base URL", () => {
      const result = getProviderBaseUrl(mockServiceNowProvider);
      expect(result).toBe("https://company.service-now.com");
    });

    it("should extract Jira base URL", () => {
      const result = getProviderBaseUrl(mockJiraProvider);
      expect(result).toBe("https://company.atlassian.net");
    });

    it("should extract Zendesk domain", () => {
      const result = getProviderBaseUrl(mockZendeskProvider);
      expect(result).toBe("https://company.zendesk.com");
    });

    it("should return empty string for provider without authentication", () => {
      const providerWithoutAuth = { ...mockServiceNowProvider, details: { authentication: {} } };
      const result = getProviderBaseUrl(providerWithoutAuth);
      expect(result).toBe("");
    });
  });

  describe("getTicketViewUrl", () => {
    it("should get ticket URL from incident enrichments for ServiceNow", () => {
      const incident = createMockIncident({
        servicenow_ticket_url: "https://company.service-now.com/now/nav/ui/classic/params/target/incident.do%3Fsys_id%3DINC0012345"
      });
      const result = getTicketViewUrl(incident, mockServiceNowProvider);
      expect(result).toBe("https://company.service-now.com/now/nav/ui/classic/params/target/incident.do%3Fsys_id%3DINC0012345");
    });

    it("should get ticket URL from incident enrichments for Jira", () => {
      const incident = createMockIncident({
        jira_ticket_url: "https://company.atlassian.net/browse/PROJ-123"
      });
      const result = getTicketViewUrl(incident, mockJiraProvider);
      expect(result).toBe("https://company.atlassian.net/browse/PROJ-123");
    });

    it("should get ticket URL from incident enrichments for Zendesk", () => {
      const incident = createMockIncident({
        zendesk_ticket_url: "https://company.zendesk.com/agent/tickets/12345"
      });
      const result = getTicketViewUrl(incident, mockZendeskProvider);
      expect(result).toBe("https://company.zendesk.com/agent/tickets/12345");
    });

    it("should return empty string when no ticket URL in enrichments", () => {
      const incident = createMockIncident({});
      const result = getTicketViewUrl(incident, mockServiceNowProvider);
      expect(result).toBe("");
    });

    it("should return empty string when incident has no enrichments", () => {
      const incident = createMockIncident();
      const result = getTicketViewUrl(incident, mockServiceNowProvider);
      expect(result).toBe("");
    });
  });

  describe("getTicketCreateUrl", () => {
    it("should construct ServiceNow create URL with parameters", () => {
      const result = getTicketCreateUrl(mockServiceNowProvider, "Test description", "Test title");
      expect(result).toBe("https://company.service-now.com/now/sow/record/incident/-1/params/short_description=Test title^description=Test description");
    });

    it("should construct Jira create URL with parameters", () => {
      const result = getTicketCreateUrl(mockJiraProvider, "Test description", "Test title");
      expect(result).toBe("https://company.atlassian.net/secure/CreateIssue.jspa/title=Test title^description=Test description");
    });

    it("should construct Zendesk create URL with parameters", () => {
      const result = getTicketCreateUrl(mockZendeskProvider, "Test description", "Test title");
      expect(result).toBe("https://company.zendesk.com/agent/filters/new/title=Test title^description=Test description");
    });

    it("should handle empty parameters", () => {
      const result = getTicketCreateUrl(mockJiraProvider);
      expect(result).toBe("https://company.atlassian.net/secure/CreateIssue.jspa/title=^description=");
    });

    it("should use configured ticket creation URL when available", () => {
      const providerWithCustomUrl = {
        ...mockServiceNowProvider,
        details: {
          authentication: {
            ...mockServiceNowProvider.details.authentication,
            ticket_creation_url: "https://custom.service-now.com/custom/create"
          }
        }
      };
      const result = getTicketCreateUrl(providerWithCustomUrl, "Test description", "Test title");
      expect(result).toBe("https://custom.service-now.com/custom/create/short_description=Test title^description=Test description");
    });
  });

  describe("findLinkedTicket", () => {
    it("should find linked ticket for ServiceNow", () => {
      const incident = createMockIncident({
        servicenow_ticket_id: "INC0012345"
      });
      const result = findLinkedTicket(incident, [mockServiceNowProvider]);
      expect(result).toEqual({
        provider: mockServiceNowProvider,
        ticketId: "INC0012345",
        key: "servicenow_ticket_id"
      });
    });

    it("should return null when no linked ticket found", () => {
      const incident = createMockIncident({});
      const result = findLinkedTicket(incident, [mockServiceNowProvider]);
      expect(result).toBeNull();
    });

    it("should return null when incident has no enrichments", () => {
      const incident = createMockIncident();
      const result = findLinkedTicket(incident, [mockServiceNowProvider]);
      expect(result).toBeNull();
    });
  });

  describe("getTicketEnrichmentKey", () => {
    it("should return correct enrichment key for ServiceNow", () => {
      const result = getTicketEnrichmentKey(mockServiceNowProvider);
      expect(result).toBe("servicenow_ticket_id");
    });

    it("should return correct enrichment key for Jira", () => {
      const result = getTicketEnrichmentKey(mockJiraProvider);
      expect(result).toBe("jira_ticket_id");
    });
  });
}); 