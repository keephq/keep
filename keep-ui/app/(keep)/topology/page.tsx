import React from "react";
import { getApplications, getTopology } from "./api";
import { TopologyPageClient } from "./topology-client";
import { createServerApiClient } from "@/shared/api/server";
import { TopologyApplication, TopologyService } from "./model";
import { PageSubtitle, PageTitle } from "@/shared/ui";

export const metadata = {
  title: "Keep - Service Topology",
  description: "See service topology and information about your services",
};

type PageProps = {
  searchParams: Promise<{
    providerIds?: string[];
    services?: string[];
    environment?: string;
  }>;
};

export default async function Page(props: PageProps) {
  const searchParams = await props.searchParams;
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
          <PageTitle>Service Topology</PageTitle>
          <PageSubtitle>
            Data describing the topology of components in your environment.
          </PageSubtitle>
        </div>
      </div>
      <TopologyPageClient
        applications={applications || undefined}
        topologyServices={topologyServices || undefined}
      />
    </>
  );
}
