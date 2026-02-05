import { ApiClient } from "@/shared/api";
import { FacetDto, FacetOptionDto, FacetOptionsQuery } from "./models";

export interface InitialFacetsData {
  facets: FacetDto[];
  facetOptions?: { [key: string]: FacetOptionDto[] } | null;
}

/**
 * Returns initial facets
 * @param api
 * @param entityName
 * @returns
 */
export async function getInitialFacets(
  api: ApiClient,
  entityName: string
): Promise<FacetDto[]> {
  return await api.get<FacetDto[]>(`/${entityName}/facets`);
}

/**
 * Returns initial facets and their options
 * @param api
 * @param entityName
 * @returns
 */
export async function getInitialFacetsData(
  api: ApiClient,
  entityName: string
): Promise<InitialFacetsData> {
  const facets = await getInitialFacets(api, entityName);
  const facetOptionsQuery: FacetOptionsQuery = {
    facet_queries: facets
      .map((f) => f.id)
      .reduce((acc, id) => ({ ...acc, [id]: "" }), {}),
  };
  const facetOptions = await api.post<{ [key: string]: FacetOptionDto[] }>(
    `/${entityName}/facets/options`,
    facetOptionsQuery
  );

  return { facets, facetOptions };
}
