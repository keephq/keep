export interface FacetOptionDto {
    display_name: string;
    value: any;
    count: number;
}

export interface FacetDto {
    id: string;
    name: string;
    is_static: boolean;
    is_lazy: boolean;
    options: FacetOptionDto[];
}
