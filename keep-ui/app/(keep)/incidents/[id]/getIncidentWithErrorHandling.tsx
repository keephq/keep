import { getIncident } from "@/entities/incidents/api/incidents";
import { getServerApiClient } from "@/shared/lib/api/getServerApiClient";
import { notFound } from "next/navigation";
import { KeepApiError } from "@/shared/lib/api/KeepApiError";
import { IncidentDto } from "@/entities/incidents/model";

export async function getIncidentWithErrorHandling(
  id: string,
  redirect = true
  // @ts-ignore ignoring since not found will be handled by nextjs
): Promise<IncidentDto> {
  try {
    const api = await getServerApiClient();
    const incident = await getIncident(api, id);
    return incident;
  } catch (error) {
    if (error instanceof KeepApiError && error.statusCode === 404 && redirect) {
      notFound();
    } else {
      throw error;
    }
  }
}
