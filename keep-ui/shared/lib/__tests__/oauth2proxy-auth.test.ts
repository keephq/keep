import {
  getOAuth2HeaderConfig,
  authorizeOAuth2Proxy,
  OAuth2HeaderConfig,
} from "../oauth2proxy-auth";

describe("getOAuth2HeaderConfig", () => {
  const originalEnv = process.env;

  beforeEach(() => {
    jest.resetModules();
    process.env = { ...originalEnv };
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  it("returns default header names when no env vars are set", () => {
    delete process.env.KEEP_OAUTH2_PROXY_USER_HEADER;
    delete process.env.KEEP_OAUTH2_PROXY_EMAIL_HEADER;
    delete process.env.KEEP_OAUTH2_PROXY_ACCESS_TOKEN_HEADER;
    delete process.env.KEEP_OAUTH2_PROXY_ROLE_HEADER;

    const config = getOAuth2HeaderConfig();

    expect(config).toEqual({
      userHeader: "x-forwarded-user",
      emailHeader: "x-forwarded-email",
      accessTokenHeader: "x-forwarded-access-token",
      groupsHeader: "x-forwarded-groups",
    });
  });

  it("reads custom header names from env vars", () => {
    process.env.KEEP_OAUTH2_PROXY_USER_HEADER = "X-Auth-Request-User";
    process.env.KEEP_OAUTH2_PROXY_EMAIL_HEADER = "X-Auth-Request-Email";
    process.env.KEEP_OAUTH2_PROXY_ACCESS_TOKEN_HEADER =
      "X-Auth-Request-Access-Token";
    process.env.KEEP_OAUTH2_PROXY_ROLE_HEADER = "X-Auth-Request-Groups";

    const config = getOAuth2HeaderConfig();

    expect(config).toEqual({
      userHeader: "x-auth-request-user",
      emailHeader: "x-auth-request-email",
      accessTokenHeader: "x-auth-request-access-token",
      groupsHeader: "x-auth-request-groups",
    });
  });

  it("lowercases env var values", () => {
    process.env.KEEP_OAUTH2_PROXY_USER_HEADER = "X-CUSTOM-USER";

    const config = getOAuth2HeaderConfig();

    expect(config.userHeader).toBe("x-custom-user");
  });
});

describe("authorizeOAuth2Proxy", () => {
  const defaultConfig: OAuth2HeaderConfig = {
    userHeader: "x-forwarded-user",
    emailHeader: "x-forwarded-email",
    accessTokenHeader: "x-forwarded-access-token",
    groupsHeader: "x-forwarded-groups",
  };

  function makeHeaders(map: Record<string, string>): Headers {
    return new Headers(map);
  }

  it("returns user with name from user header and email from email header", () => {
    const headers = makeHeaders({
      "x-forwarded-user": "John Doe",
      "x-forwarded-email": "john@example.com",
      "x-forwarded-access-token": "token-abc",
      "x-forwarded-groups": "admin",
    });

    const user = authorizeOAuth2Proxy(headers, defaultConfig);

    expect(user).not.toBeNull();
    expect(user!.name).toBe("John Doe");
    expect(user!.email).toBe("john@example.com");
    expect(user!.id).toBe("john@example.com");
    expect(user!.accessToken).toBe("token-abc");
    expect(user!.role).toBe("admin");
  });

  it("uses user header as fallback when email header is missing", () => {
    const headers = makeHeaders({
      "x-forwarded-user": "Jane Doe",
    });

    const user = authorizeOAuth2Proxy(headers, defaultConfig);

    expect(user).not.toBeNull();
    expect(user!.name).toBe("Jane Doe");
    expect(user!.email).toBe("Jane Doe");
    expect(user!.id).toBe("Jane Doe");
  });

  it("uses email header as fallback when user header is missing", () => {
    const headers = makeHeaders({
      "x-forwarded-email": "jane@example.com",
    });

    const user = authorizeOAuth2Proxy(headers, defaultConfig);

    expect(user).not.toBeNull();
    expect(user!.name).toBe("jane@example.com");
    expect(user!.email).toBe("jane@example.com");
    expect(user!.id).toBe("jane@example.com");
  });

  it("returns null when no identity headers are present", () => {
    const headers = makeHeaders({});
    const consoleSpy = jest.spyOn(console, "error").mockImplementation();

    const user = authorizeOAuth2Proxy(headers, defaultConfig);

    expect(user).toBeNull();
    expect(consoleSpy).toHaveBeenCalledWith(
      "OAuth2Proxy: No user identity found in headers.",
      "Expected headers:",
      defaultConfig
    );
    consoleSpy.mockRestore();
  });

  it("synthesizes access token from identity when no access token header is present", () => {
    const headers = makeHeaders({
      "x-forwarded-user": "Test User",
      "x-forwarded-email": "test@example.com",
    });

    const user = authorizeOAuth2Proxy(headers, defaultConfig);

    expect(user).not.toBeNull();
    expect(user!.accessToken).toBe("oauth2proxy:Test User");
  });

  it("synthesizes access token from email when only email is present", () => {
    const headers = makeHeaders({
      "x-forwarded-email": "only-email@example.com",
    });

    const user = authorizeOAuth2Proxy(headers, defaultConfig);

    expect(user).not.toBeNull();
    expect(user!.accessToken).toBe("oauth2proxy:only-email@example.com");
  });

  it("sets role to undefined when groups header is missing", () => {
    const headers = makeHeaders({
      "x-forwarded-user": "Test User",
    });

    const user = authorizeOAuth2Proxy(headers, defaultConfig);

    expect(user).not.toBeNull();
    expect(user!.role).toBeUndefined();
  });

  it("works with custom header config", () => {
    const customConfig: OAuth2HeaderConfig = {
      userHeader: "x-auth-request-user",
      emailHeader: "x-auth-request-email",
      accessTokenHeader: "x-auth-request-access-token",
      groupsHeader: "x-auth-request-groups",
    };

    const headers = makeHeaders({
      "x-auth-request-user": "Custom User",
      "x-auth-request-email": "custom@example.com",
      "x-auth-request-access-token": "custom-token",
      "x-auth-request-groups": "noc",
    });

    const user = authorizeOAuth2Proxy(headers, customConfig);

    expect(user).not.toBeNull();
    expect(user!.name).toBe("Custom User");
    expect(user!.email).toBe("custom@example.com");
    expect(user!.accessToken).toBe("custom-token");
    expect(user!.role).toBe("noc");
  });

  it("ignores unrelated headers", () => {
    const headers = makeHeaders({
      "x-forwarded-user": "Real User",
      "x-unrelated-header": "noise",
      authorization: "Bearer something",
    });

    const user = authorizeOAuth2Proxy(headers, defaultConfig);

    expect(user).not.toBeNull();
    expect(user!.name).toBe("Real User");
  });

  it("prefers user header over email header for the name field", () => {
    const headers = makeHeaders({
      "x-forwarded-user": "Display Name",
      "x-forwarded-email": "email@example.com",
    });

    const user = authorizeOAuth2Proxy(headers, defaultConfig);

    expect(user!.name).toBe("Display Name");
    expect(user!.email).toBe("email@example.com");
  });

  it("prefers email header over user header for the id field", () => {
    const headers = makeHeaders({
      "x-forwarded-user": "Display Name",
      "x-forwarded-email": "email@example.com",
    });

    const user = authorizeOAuth2Proxy(headers, defaultConfig);

    expect(user!.id).toBe("email@example.com");
  });
});
