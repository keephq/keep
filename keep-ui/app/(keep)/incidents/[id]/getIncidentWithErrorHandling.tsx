import { getIncident } from "@/entities/incidents/api/incidents";
import { createServerApiClient } from "@/shared/api/server";
import { notFound } from "next/navigation";
import { KeepApiError } from "@/shared/api";
import { IncidentDto } from "@/entities/incidents/model";

export async function getIncidentWithErrorHandling(
  id: string,
  redirect = true
  // @ts-ignore ignoring since not found will be handled by nextjs
): Promise<IncidentDto> {
  try {
    const api = await createServerApiClient();
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
