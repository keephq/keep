import { IncidentList } from "features/incidents/incident-list";
import { createServerApiClient } from "@/shared/api/server";
import { getInitialFacets } from "@/features/filter/api";
import { FacetDto } from "@/features/filter";

export default async function Page() {
  let initialFacets: FacetDto[] | null = null;

  try {
    const api = await createServerApiClient();

    const tasks = [getInitialFacets(api, "incidents")];
    const [_incidents, _facetsData] = await Promise.all(tasks);
    initialFacets = _facetsData as FacetDto[];
  } catch (error) {
    console.log(error);
  }
  return (
    <IncidentList
      initialFacetsData={
        initialFacets
          ? { facets: initialFacets, facetOptions: null }
          : undefined
      }
    />
  );
}

export const metadata = {
  title: "Keep - Incidents",
  description: "List of incidents",
};
