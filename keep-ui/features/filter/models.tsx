export interface FacetOptionDto {
    display_name: string;
    value: any;
    matches_count: number;
}

export interface FacetOptionsQuery {
    facet_id: string;
    cel: string;
}

export type FacetOptionsQueries = { [facet_id: string]: string };

export interface FacetDto {
    id: string;
    property_path: string;
    name: string;
    is_static: boolean;
    is_lazy: boolean;
}

export interface CreateFacetDto {
    property_path: string;
    name: string;
}
