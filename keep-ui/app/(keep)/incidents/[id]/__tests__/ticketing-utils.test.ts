import { 
  getProviderBaseUrl, 
  getTicketViewUrl, 
  getTicketCreateUrl, 
  findLinkedTicket,
  getTicketEnrichmentKey,
  type LinkedTicket 
} from "../ticketing-utils";
import { type Provider } from "@/shared/api/providers";

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
      service_now_base_url: "https://company.service-now.com"
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
      jira_base_url: "https://company.atlassian.net"
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
      zendesk_domain: "company.zendesk.com"
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
    it("should construct ServiceNow ticket URL", () => {
      const linkedTicket: LinkedTicket = {
        provider: mockServiceNowProvider,
        ticketId: "INC0012345",
        key: "servicenow_ticket_id"
      };
      const result = getTicketViewUrl(linkedTicket);
      expect(result).toBe("https://company.service-now.com/now/nav/ui/classic/params/target/incident.do%3Fsys_id%3DINC0012345");
    });

    it("should construct Jira ticket URL", () => {
      const linkedTicket: LinkedTicket = {
        provider: mockJiraProvider,
        ticketId: "PROJ-123",
        key: "jira_ticket_id"
      };
      const result = getTicketViewUrl(linkedTicket);
      expect(result).toBe("https://company.atlassian.net/browse/PROJ-123");
    });

    it("should construct Zendesk ticket URL", () => {
      const linkedTicket: LinkedTicket = {
        provider: mockZendeskProvider,
        ticketId: "12345",
        key: "zendesk_ticket_id"
      };
      const result = getTicketViewUrl(linkedTicket);
      expect(result).toBe("https://company.zendesk.com/agent/tickets/12345");
    });

    it("should return empty string for provider without base URL", () => {
      const providerWithoutAuth = { ...mockServiceNowProvider, details: { authentication: {} } };
      const linkedTicket: LinkedTicket = {
        provider: providerWithoutAuth,
        ticketId: "INC0012345",
        key: "servicenow_ticket_id"
      };
      const result = getTicketViewUrl(linkedTicket);
      expect(result).toBe("");
    });
  });

  describe("getTicketCreateUrl", () => {
    it("should construct ServiceNow create URL with parameters", () => {
      const result = getTicketCreateUrl(mockServiceNowProvider, "Test description", "Test title");
      expect(result).toContain("https://company.service-now.com/now/sow/record/incident/-1/params/short_description=Test title&description=Test description");
    });

    it("should construct Jira create URL with parameters", () => {
      const result = getTicketCreateUrl(mockJiraProvider, "Test description", "Test title");
      expect(result).toBe("https://company.atlassian.net/secure/CreateIssue.jspa");
    });

    it("should construct Zendesk create URL with parameters", () => {
      const result = getTicketCreateUrl(mockZendeskProvider, "Test description", "Test title");
      expect(result).toBe("https://company.zendesk.com/agent/filters/new");
    });

    it("should handle empty parameters", () => {
      const result = getTicketCreateUrl(mockJiraProvider);
      expect(result).toBe("https://company.atlassian.net/secure/CreateIssue.jspa");
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
      expect(result).toBe("https://custom.service-now.com/custom/create");
    });
  });

  describe("findLinkedTicket", () => {
    it("should find ServiceNow linked ticket", () => {
      const incident = {
        enrichments: {
          servicenow_ticket_id: "INC0012345"
        }
      };
      const providers = [mockServiceNowProvider, mockJiraProvider];
      const result = findLinkedTicket(incident, providers);
      
      expect(result).toEqual({
        provider: mockServiceNowProvider,
        ticketId: "INC0012345",
        key: "servicenow_ticket_id"
      });
    });

    it("should find Jira linked ticket", () => {
      const incident = {
        enrichments: {
          jira_ticket_id: "PROJ-123"
        }
      };
      const providers = [mockServiceNowProvider, mockJiraProvider];
      const result = findLinkedTicket(incident, providers);
      
      expect(result).toEqual({
        provider: mockJiraProvider,
        ticketId: "PROJ-123",
        key: "jira_ticket_id"
      });
    });

    it("should return null when no linked ticket found", () => {
      const incident = {
        enrichments: {
          some_other_field: "value"
        }
      };
      const providers = [mockServiceNowProvider, mockJiraProvider];
      const result = findLinkedTicket(incident, providers);
      
      expect(result).toBeNull();
    });

    it("should return null when no enrichments", () => {
      const incident = {};
      const providers = [mockServiceNowProvider, mockJiraProvider];
      const result = findLinkedTicket(incident, providers);
      
      expect(result).toBeNull();
    });
  });

  describe("getTicketEnrichmentKey", () => {
    it("should generate correct enrichment key for ServiceNow", () => {
      const result = getTicketEnrichmentKey(mockServiceNowProvider);
      expect(result).toBe("servicenow_ticket_id");
    });

    it("should generate correct enrichment key for Jira", () => {
      const result = getTicketEnrichmentKey(mockJiraProvider);
      expect(result).toBe("jira_ticket_id");
    });

    it("should generate correct enrichment key for Zendesk", () => {
      const result = getTicketEnrichmentKey(mockZendeskProvider);
      expect(result).toBe("zendesk_ticket_id");
    });
  });
}); 