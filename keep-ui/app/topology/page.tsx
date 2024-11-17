import React from "react";

import { getServerSession } from "next-auth/next";
import { authOptions } from "@/pages/api/auth/[...nextauth]";
import { getApplications, getTopology } from "./api";
import { TopologyPageClient } from "./topology-client";
import { Subtitle, Title } from "@tremor/react";
import { getApiURL } from "@/utils/apiUrl";

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
  const session = await getServerSession(authOptions);
  const apiUrl = getApiURL();

  const applications = await getApplications(apiUrl, session);
  const topologyServices = await getTopology(apiUrl, session, {
    providerIds: searchParams.providerIds,
    services: searchParams.services,
    environment: searchParams.environment,
  });

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
