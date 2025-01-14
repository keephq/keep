import { ApiClient } from "@/shared/api";
import { FacetDto, FacetOptionDto } from "./models";

export interface InitialFacetsData {
  facets: FacetDto[];
  facetOptions: { [key: string]: FacetOptionDto[] };
}

export async function getInitialFacets(
  api: ApiClient,
  entityType: string
): Promise<InitialFacetsData> {
  const facets = await api.get<FacetDto[]>(`/${entityType}/facets`);
  const facetOptions = await api.get<{ [key: string]: FacetOptionDto[] }>(
    `/${entityType}/facets/options?facets_to_load=${facets.map((f) => f.id).join(",")}`
  );

  return { facets, facetOptions };
}
