import { getIncident } from "@/entities/incidents/api/incidents";
import { getServerSession } from "next-auth";
import { getApiURL } from "@/utils/apiUrl";
import { authOptions } from "@/pages/api/auth/[...nextauth]";

import { notFound } from "next/navigation";

export async function getIncidentWithErrorHandling(id: string) {
  try {
    const session = await getServerSession(authOptions);
    const apiUrl = getApiURL();
    const incident = await getIncident(apiUrl, session, id);
    if (!incident) {
      return notFound();
    }
    return incident;
  } catch (error) {
    // You can handle different error cases here
    throw error; // This will trigger Next.js error boundary
  }
}
