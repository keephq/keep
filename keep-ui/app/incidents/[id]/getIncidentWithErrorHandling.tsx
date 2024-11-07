import { getIncident } from "@/entities/incidents/api/incidents";
import { getServerSession } from "next-auth";
import { getApiURL } from "@/utils/apiUrl";
import { authOptions } from "@/pages/api/auth/[...nextauth]";

import { notFound } from "next/navigation";
import { KeepApiError } from "@/shared/lib/KeepApiError";
import { IncidentDto } from "@/entities/incidents/model";

export async function getIncidentWithErrorHandling(
  id: string,
  redirect = true
  // @ts-ignore ignoring since not found will be handled by nextjs
): Promise<IncidentDto> {
  try {
    const session = await getServerSession(authOptions);
    const apiUrl = getApiURL();
    const incident = await getIncident(apiUrl, session, id);
    return incident;
  } catch (error) {
    if (error instanceof KeepApiError && error.statusCode === 404 && redirect) {
      notFound();
    } else {
      throw error;
    }
  }
}
