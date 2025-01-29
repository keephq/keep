import { ApiClient } from "@/shared/api";
import { FacetDto, FacetOptionDto, FacetOptionsQuery } from "./models";

export interface InitialFacetsData {
  facets: FacetDto[];
  facetOptions: { [key: string]: FacetOptionDto[] };
}

export async function getInitialFacets(
  api: ApiClient,
  entityName: string
): Promise<InitialFacetsData> {
  const facets = await api.get<FacetDto[]>(`/${entityName}/facets`);
  const facetOptionsQuery: FacetOptionsQuery = { facet_queries: facets.map((f) => f.id).reduce((acc, id) => ({...acc, [id]: ''}), {}) };
  const facetOptions = await api.post<{ [key: string]: FacetOptionDto[] }>(
    `/${entityName}/facets/options`,
    facetOptionsQuery
  );

  return { facets, facetOptions };
}
