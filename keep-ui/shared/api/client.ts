import { ApiClient } from "./ApiClient";
import { GuestSession } from "@/types/auth";

// Singleton instance for client-side
let clientInstance: ApiClient | null = null;

export function createApiClient(session: any, config: any) {
  return new ApiClient(session, config);
}

// For client-side use outside of React components
export function getClientApiInstance() {
  if (!clientInstance) {
    // Default to guest session if not initialized
    clientInstance = createApiClient(
      { accessToken: "unauthenticated" } as GuestSession,
      {}
    );
  }
  return clientInstance;
}

// Update the client instance (called by useApi hook)
export function updateClientInstance(newInstance: ApiClient) {
  clientInstance = newInstance;
}
