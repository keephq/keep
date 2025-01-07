export interface FacetOptionDto {
    displayName: string;
    value: any;
    count: number;
}

export interface FacetDto {
    id: string;
    name: string;
    isStatic: boolean;
    options: FacetOptionDto[];
}
