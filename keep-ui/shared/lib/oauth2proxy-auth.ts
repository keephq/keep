import type { User } from "next-auth";

export interface OAuth2HeaderConfig {
  userHeader: string;
  emailHeader: string;
  accessTokenHeader: string;
  groupsHeader: string;
}

export function getOAuth2HeaderConfig(): OAuth2HeaderConfig {
  return {
    userHeader:
      process.env.KEEP_OAUTH2_PROXY_USER_HEADER?.toLowerCase() ||
      "x-forwarded-user",
    emailHeader:
      process.env.KEEP_OAUTH2_PROXY_EMAIL_HEADER?.toLowerCase() ||
      "x-forwarded-email",
    accessTokenHeader:
      process.env.KEEP_OAUTH2_PROXY_ACCESS_TOKEN_HEADER?.toLowerCase() ||
      "x-forwarded-access-token",
    groupsHeader:
      process.env.KEEP_OAUTH2_PROXY_ROLE_HEADER?.toLowerCase() ||
      "x-forwarded-groups",
  };
}

export function authorizeOAuth2Proxy(
  headers: Headers,
  headerConfig?: OAuth2HeaderConfig
): User | null {
  const config = headerConfig ?? getOAuth2HeaderConfig();

  const userValue = headers.get(config.userHeader);
  const emailValue = headers.get(config.emailHeader);
  const accessToken = headers.get(config.accessTokenHeader);
  const groups = headers.get(config.groupsHeader);

  const identity = userValue || emailValue;
  if (!identity) {
    console.error(
      "OAuth2Proxy: No user identity found in headers.",
      "Expected headers:",
      config
    );
    return null;
  }

  return {
    id: emailValue || userValue || "oauth2proxy-user",
    name: userValue || emailValue || "OAuth2Proxy User",
    email: emailValue || userValue || "oauth2proxy-user",
    accessToken: accessToken || `oauth2proxy:${identity}`,
    role: groups || undefined,
  };
}
