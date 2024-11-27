import React from "react";
import { getApplications, getTopology } from "./api";
import { TopologyPageClient } from "./topology-client";
import { Subtitle, Title } from "@tremor/react";
import { createServerApiClient } from "@/shared/api/server";
import { TopologyApplication, TopologyService } from "./model";

export const metadata = {
  title: "Keep - Service Topology",
  description: "See service topology and information about your services",
};

type PageProps = {
  searchParams: {
    providerIds?: string[];
    services?: string[];
    environment?: string;
  };
};

export default async function Page({ searchParams }: PageProps) {
  const api = await createServerApiClient();

  let applications: TopologyApplication[] | undefined;
  let topologyServices: TopologyService[] | undefined;

  try {
    applications = await getApplications(api);
    topologyServices = await getTopology(api, {
      providerIds: searchParams.providerIds,
      services: searchParams.services,
      environment: searchParams.environment,
    });
  } catch (error) {
    console.error(error);
  }

  return (
    <>
      <div className="flex w-full justify-between items-center mb-2">
        <div>
          <Title>Service Topology</Title>
          <Subtitle>
            Data describing the topology of components in your environment.
          </Subtitle>
        </div>
      </div>
      <TopologyPageClient
        applications={applications || undefined}
        topologyServices={topologyServices || undefined}
      />
    </>
  );
}
