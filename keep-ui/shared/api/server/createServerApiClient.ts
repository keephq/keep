import { auth } from "@/auth";
import { getConfig } from "@/shared/lib/server/getConfig";
import { ApiClient } from "../ApiClient";
import { AuthType } from "@/utils/authenticationType";
import { headers } from "next/headers";

interface OAuth2ProxyHeaderConfig {
  userHeader: string;
  emailHeader: string;
  accessTokenHeader: string;
  groupsHeader: string;
}

const DEFAULT_OAUTH2_HEADERS: OAuth2ProxyHeaderConfig = {
  userHeader: "x-forwarded-user",
  emailHeader: "x-forwarded-email",
  accessTokenHeader: "x-forwarded-access-token",
  groupsHeader: "x-forwarded-groups",
};

function getOAuth2HeaderConfig(): OAuth2ProxyHeaderConfig {
  return {
    userHeader:
      process.env.KEEP_OAUTH2_PROXY_USER_HEADER?.toLowerCase() ||
      DEFAULT_OAUTH2_HEADERS.userHeader,
    emailHeader:
      process.env.KEEP_OAUTH2_PROXY_EMAIL_HEADER?.toLowerCase() ||
      DEFAULT_OAUTH2_HEADERS.emailHeader,
    accessTokenHeader:
      process.env.KEEP_OAUTH2_PROXY_ACCESS_TOKEN_HEADER?.toLowerCase() ||
      DEFAULT_OAUTH2_HEADERS.accessTokenHeader,
    groupsHeader:
      process.env.KEEP_OAUTH2_PROXY_ROLE_HEADER?.toLowerCase() ||
      DEFAULT_OAUTH2_HEADERS.groupsHeader,
  };
}

/**
 * Creates an API client configured for server-side usage
 * @throws {Error} If authentication fails or configuration cannot be loaded
 * @returns {Promise<ApiClient>} Configured API client instance
 */
export async function createServerApiClient(): Promise<ApiClient> {
  try {
    const session = await auth();
    const config = getConfig();

    // Only process OAuth2Proxy headers if AUTH_TYPE matches
    if (process.env.AUTH_TYPE === AuthType.OAUTH2PROXY) {
      console.log("Using OAuth2Proxy headers");
      const headersList = headers();
      const oauth2Headers: Record<string, string> = {};
      const headerConfig = getOAuth2HeaderConfig();
      console.log("OAuth2Proxy header config:", headerConfig);

      // Map of target header names to their configured source header names
      const headerMappings: Record<string, string> = {
        "x-forwarded-user": headerConfig.userHeader,
        "x-forwarded-email": headerConfig.emailHeader,
        "x-forwarded-access-token": headerConfig.accessTokenHeader,
        "x-forwarded-groups": headerConfig.groupsHeader,
      };

      // Extract headers using the configured names but store with standard names
      for (const [standardName, configuredName] of Object.entries(
        headerMappings
      )) {
        // Use get() method directly on headersList
        const value = headersList.get(configuredName);
        console.log(`Extracted ${configuredName} header:`, value);
        if (value) {
          console.log(`Storing ${standardName} header:`, value);
          oauth2Headers[standardName] = value;
        }
      }

      console.log("OAuth2Proxy headers:", oauth2Headers);
      return new ApiClient(session, config, { headers: oauth2Headers });
    }

    return new ApiClient(session, config);
  } catch (error: unknown) {
    if (error instanceof Error) {
      throw new Error(`Failed to create server API client: ${error.message}`);
    }
    throw new Error("Failed to create server API client: Unknown error");
  }
}
