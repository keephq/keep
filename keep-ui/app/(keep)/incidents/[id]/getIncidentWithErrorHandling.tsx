import { getIncident } from "@/entities/incidents/api";
import { createServerApiClient } from "@/shared/api/server";
import { notFound } from "next/navigation";
import { KeepApiError } from "@/shared/api";
import { IncidentDto } from "@/entities/incidents/model";
import { cache } from "react";

async function _getIncidentWithErrorHandling(
  id: string
  // @ts-ignore ignoring since not found will be handled by nextjs
): Promise<IncidentDto> {
  try {
    const api = await createServerApiClient();
    const incident = await getIncident(api, id);
    return incident;
  } catch (error) {
    if (error instanceof KeepApiError && error.statusCode === 404) {
      notFound();
    } else {
      throw error;
    }
  }
}

// cache the function for server side, so we can use it in the layout, metadata and in the page itself
export const getIncidentWithErrorHandling = cache(
  _getIncidentWithErrorHandling
);
