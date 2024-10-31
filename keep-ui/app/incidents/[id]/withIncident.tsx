import { getIncident } from "@/entities/incidents/api/incidents";
import { IncidentDto } from "../models";
import { getServerSession } from "next-auth";
import { getApiURL } from "@/utils/apiUrl";
import { authOptions } from "@/pages/api/auth/[...nextauth]";
import { Title } from "@tremor/react";
import { Metadata } from "next";

export async function withIncident(
  Component: React.ComponentType<{ incident: IncidentDto }>
) {
  return async function WithIncident(props: { params: { id: string } }) {
    if (!props.params.id) {
      return <Title>Incident ID is required</Title>;
    }
    try {
      const session = await getServerSession(authOptions);
      const apiUrl = getApiURL();
      const incident = await getIncident(apiUrl, session, props.params.id);
      return <Component incident={incident} />;
    } catch (error) {
      return <Title>Incident with id {props.params.id} does not exist.</Title>;
    }
  };
}

export function withIncidentMetadata(
  generateMetadata: (incident: IncidentDto) => Metadata
) {
  return async function withIncidentMetadataFunction(props: {
    params: { id: string };
  }) {
    const session = await getServerSession(authOptions);
    const apiUrl = getApiURL();
    const incident = await getIncident(apiUrl, session, props.params.id);
    return generateMetadata(incident);
  };
}
