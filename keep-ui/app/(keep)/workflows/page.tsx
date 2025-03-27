import React from "react";
import { WorkflowsPage } from "./workflows.client";
import { FacetDto } from "@/features/filter";
import { createServerApiClient } from "@/shared/api/server";
import { getInitialFacets } from "@/features/filter/api";

export default async function Page() {
  let initialFacets: FacetDto[] | null = null;

  try {
    const api = await createServerApiClient();
    initialFacets = await getInitialFacets(api, "workflows");
  } catch (error) {
    console.log(error);
  }
  return (
    <WorkflowsPage
      initialFacetsData={
        initialFacets
          ? { facets: initialFacets, facetOptions: null }
          : undefined
      }
    />
  );
}

export const metadata = {
  title: "Keep - Workflows",
  description: "Automate your workflows with Keep.",
};
