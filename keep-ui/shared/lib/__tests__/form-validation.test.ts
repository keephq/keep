import { getZodSchema } from "../../../app/(keep)/providers/form-validation";
import { Provider } from "@/shared/api/providers";

describe("provider form validation", () => {
  describe("getZodSchema", () => {
    it("validates required fields including provider_name", () => {
      const config: Provider["config"] = {
        api_key: {
          description: "API Key",
          required: true,
          default: null,
        },
      };

      const schema = getZodSchema(config, false);

      // Invalid missing fields
      const invalidResult = schema.safeParse({});
      expect(invalidResult.success).toBe(false);
      if (!invalidResult.success) {
        const errorKeys = invalidResult.error.issues.map((i) => i.path[0]);
        expect(errorKeys).toContain("provider_name");
        expect(errorKeys).toContain("api_key");
      }

      // Valid fields
      const validResult = schema.safeParse({
        provider_name: "my-provider",
        api_key: "secret123",
      });
      expect(validResult.success).toBe(true);
    });

    it("validates https_url validation type", () => {
      const config: Provider["config"] = {
        host: {
          description: "Jira Host",
          required: true,
          validation: "https_url",
          default: null,
        },
      };

      const schema = getZodSchema(config, false);

      // Invalid protocol
      const httpResult = schema.safeParse({
        provider_name: "jira",
        host: "http://keephq.atlassian.net",
      });
      expect(httpResult.success).toBe(false);

      // Invalid URL format
      const invalidUrlResult = schema.safeParse({
        provider_name: "jira",
        host: "invalid url host",
      });
      expect(invalidUrlResult.success).toBe(false);

      // Valid https URL
      const validResult = schema.safeParse({
        provider_name: "jira",
        host: "https://keephq.atlassian.net",
      });
      expect(validResult.success).toBe(true);
    });

    it("validates any_http_url validation type", () => {
      const config: Provider["config"] = {
        host: {
          description: "GitLab Host",
          required: true,
          validation: "any_http_url",
          default: null,
        },
      };

      const schema = getZodSchema(config, false);

      // Valid http
      expect(
        schema.safeParse({
          provider_name: "gitlab",
          host: "http://gitlab.internal.local",
        }).success
      ).toBe(true);

      // Valid https
      expect(
        schema.safeParse({
          provider_name: "gitlab",
          host: "https://gitlab.com",
        }).success
      ).toBe(true);

      // Invalid ftp scheme
      expect(
        schema.safeParse({
          provider_name: "gitlab",
          host: "ftp://gitlab.com",
        }).success
      ).toBe(false);
    });

    it("validates no_scheme_url validation type", () => {
      const config: Provider["config"] = {
        host: {
          description: "Database Host",
          required: true,
          validation: "no_scheme_url",
          default: null,
        },
      };

      const schema = getZodSchema(config, false);

      // Valid without scheme
      expect(
        schema.safeParse({
          provider_name: "db",
          host: "db.example.com",
        }).success
      ).toBe(true);

      // Valid IP address
      expect(
        schema.safeParse({
          provider_name: "db",
          host: "192.168.1.1",
        }).success
      ).toBe(true);

      // Invalid host characters
      expect(
        schema.safeParse({
          provider_name: "db",
          host: "invalid@host!name",
        }).success
      ).toBe(false);
    });

    it("validates port validation type", () => {
      const config: Provider["config"] = {
        port: {
          description: "Service Port",
          required: true,
          validation: "port",
          default: null,
        },
      };

      const schema = getZodSchema(config, false);

      // Valid port string
      expect(
        schema.safeParse({
          provider_name: "svc",
          port: "8080",
        }).success
      ).toBe(true);

      // Invalid port numbers
      expect(
        schema.safeParse({
          provider_name: "svc",
          port: "0",
        }).success
      ).toBe(false);

      expect(
        schema.safeParse({
          provider_name: "svc",
          port: "70000",
        }).success
      ).toBe(false);

      expect(
        schema.safeParse({
          provider_name: "svc",
          port: "abc",
        }).success
      ).toBe(false);
    });

    it("validates tld validation type", () => {
      const config: Provider["config"] = {
        tld: {
          description: "Domain TLD",
          required: true,
          validation: "tld",
          default: null,
        },
      };

      const schema = getZodSchema(config, false);

      // Valid TLD
      expect(
        schema.safeParse({
          provider_name: "tld-test",
          tld: ".com",
        }).success
      ).toBe(true);

      // Invalid TLD
      expect(
        schema.safeParse({
          provider_name: "tld-test",
          tld: "invalid",
        }).success
      ).toBe(false);
    });

    it("validates multihost_url and no_scheme_multihost_url validation types", () => {
      const multiConfig: Provider["config"] = {
        multihost: {
          description: "Multi Host",
          required: true,
          validation: "multihost_url",
          default: null,
        },
        no_scheme_multihost: {
          description: "No Scheme Multi Host",
          required: true,
          validation: "no_scheme_multihost_url",
          default: null,
        },
      };

      const schema = getZodSchema(multiConfig, false);

      expect(
        schema.safeParse({
          provider_name: "multi",
          multihost: "https://node1.example.com,node2.example.com",
          no_scheme_multihost: "node1.example.com,node2.example.com",
        }).success
      ).toBe(true);
    });

    it("handles optional fields correctly", () => {
      const config: Provider["config"] = {
        optional_host: {
          description: "Optional Host",
          required: false,
          validation: "https_url",
          default: null,
        },
      };

      const schema = getZodSchema(config, false);

      // Omitting optional field is valid
      expect(
        schema.safeParse({
          provider_name: "test-optional",
        }).success
      ).toBe(true);

      // Providing undefined is valid if optional
      expect(
        schema.safeParse({
          provider_name: "test-optional",
          optional_host: undefined,
        }).success
      ).toBe(true);
    });
  });
});
