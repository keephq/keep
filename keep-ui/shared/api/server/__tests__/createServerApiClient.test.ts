import { createServerApiClient } from "../createServerApiClient";
import { auth } from "@/auth";
import { getConfig } from "@/shared/lib/server/getConfig";
import { headers } from "next/headers";
import { AuthType } from "@/utils/authenticationType";

jest.mock("@/auth", () => ({
  auth: jest.fn(),
}));

jest.mock("@/shared/lib/server/getConfig", () => ({
  getConfig: jest.fn(),
}));

jest.mock("next/headers", () => ({
  headers: jest.fn(),
}));

describe("createServerApiClient", () => {
  const originalEnv = process.env;

  beforeEach(() => {
    jest.clearAllMocks();
    process.env = { ...originalEnv };
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  it("should forward cookie and user headers when AUTH_TYPE is OAUTH2PROXY", async () => {
    process.env.AUTH_TYPE = AuthType.OAUTH2PROXY;
    process.env.KEEP_OAUTH2_PROXY_USER_HEADER = "x-forwarded-user";
    process.env.KEEP_OAUTH2_PROXY_EMAIL_HEADER = "x-forwarded-email";
    process.env.KEEP_OAUTH2_PROXY_ROLE_HEADER = "x-forwarded-groups";
    process.env.KEEP_OAUTH2_PROXY_ACCESS_TOKEN_HEADER = "x-forwarded-access-token";

    (auth as jest.Mock).mockResolvedValue({
      user: { id: "1", name: "Test User", email: "test@example.com" },
      accessToken: "test-token",
    });

    (getConfig as jest.Mock).mockReturnValue({
      AUTH_TYPE: AuthType.OAUTH2PROXY,
    });

    const mockHeaders = new Map([
      ["x-forwarded-user", "test-user"],
      ["x-forwarded-email", "test@example.com"],
      ["x-forwarded-groups", "admin,noc"],
      ["x-forwarded-access-token", "jwt-token-xyz"],
      ["cookie", "_oauth2_proxy=session-cookie-val; other=123"],
    ]);

    (headers as jest.Mock).mockResolvedValue({
      get: (key: string) => mockHeaders.get(key.toLowerCase()) || null,
    });

    const client = await createServerApiClient();
    const headersResult = (client as any).getHeaders();

    expect(headersResult["x-forwarded-user"]).toBe("test-user");
    expect(headersResult["x-forwarded-email"]).toBe("test@example.com");
    expect(headersResult["x-forwarded-groups"]).toBe("admin,noc");
    expect(headersResult["x-forwarded-access-token"]).toBe("jwt-token-xyz");
    expect(headersResult["cookie"]).toBe("_oauth2_proxy=session-cookie-val; other=123");
  });

  it("should create standard client when AUTH_TYPE is not OAUTH2PROXY", async () => {
    process.env.AUTH_TYPE = AuthType.DB;

    (auth as jest.Mock).mockResolvedValue({
      user: { id: "1", name: "Test User", email: "test@example.com" },
      accessToken: "db-access-token",
    });

    (getConfig as jest.Mock).mockReturnValue({
      AUTH_TYPE: AuthType.DB,
    });

    const client = await createServerApiClient();
    const headersResult = (client as any).getHeaders();

    expect(headersResult["cookie"]).toBeUndefined();
    expect(headersResult["Authorization"]).toBe("Bearer db-access-token");
  });
});
