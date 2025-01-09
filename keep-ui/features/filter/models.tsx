export interface FacetOptionDto {
    display_name: string;
    value: any;
    matches_count: number;
}

export interface FacetDto {
    id: string;
    name: string;
    is_static: boolean;
    is_lazy: boolean;
}

export interface CreateFacetDto {
    id: string;
    name: string;
}