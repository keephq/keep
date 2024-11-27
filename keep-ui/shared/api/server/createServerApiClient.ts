import { auth } from "@/auth";
import { getConfig } from "@/shared/lib/server/getConfig";
import { ApiClient } from "../ApiClient";

/**
 * Creates an API client configured for server-side usage
 * @throws {Error} If authentication fails or configuration cannot be loaded
 * @returns {Promise<ApiClient>} Configured API client instance
 */
export async function createServerApiClient(): Promise<ApiClient> {
  try {
    const session = await auth();
    const config = getConfig();
    // true indicates server-side mode
    return new ApiClient(session, config, true);
  } catch (error: unknown) {
    if (error instanceof Error) {
      throw new Error(`Failed to create server API client: ${error.message}`);
    }
    throw new Error("Failed to create server API client: Unknown error");
  }
}
