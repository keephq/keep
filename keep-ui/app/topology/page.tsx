import { getServerSession } from "next-auth/next";
import { authOptions } from "../../pages/api/auth/[...nextauth]";
import { getApplications, getTopology } from "./data/api";
import { TopologyPageClient } from "./topology-client";
import { Subtitle, Title } from "@tremor/react";
import React from "react";

export const metadata = {
  title: "Keep - Service Topology",
  description: "See service topology and information about your services",
};

type PageProps = {
  searchParams: {
    provider?: string;
    service?: string;
    environment?: string;
  };
};

export default async function Page({ searchParams }: PageProps) {
  const session = await getServerSession(authOptions);

  const applications = await getApplications(session);
  const topologyServices = await getTopology(session, {
    providerId: searchParams.provider,
    service: searchParams.service,
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
