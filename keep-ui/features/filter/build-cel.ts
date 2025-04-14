import { FacetDto, FacetOptionDto, FacetState } from "./models";

export function buildCel(
  facets: FacetDto[],
  facetOptions: { [key: string]: FacetOptionDto[] } | null,
  facetsState: FacetState
): string {
  if (facetOptions == null) {
    return "";
  }

  const cel = Object.values(facets)
    .filter((facet) => facet.id in facetsState)
    .filter((facet) => facetOptions[facet.id])
    .map((facet) => {
      const allFacetOptions = Object.values(facetOptions[facet.id]);
      const atLeastOneUnselected = allFacetOptions.some((facetOption) =>
        facetsState[facet.id]?.has(facetOption.display_name)
      );

      if (!atLeastOneUnselected) {
        return null;
      }

      const selectedOptions = Object.values(facetOptions[facet.id])
        .filter(
          (facetOption) =>
            !facetsState[facet.id]?.has(facetOption.display_name) &&
            facetOption.matches_count > 0
        )
        .map((option) => {
          if (typeof option.value === "string") {
            /* Escape single-quote because single-quote is used for string literal mark*/
            const optionValue = option.value.replace(/'/g, "\\'");
            return `'${optionValue}'`;
          } else if (option.value == null) {
            return "null";
          }

          return option.value;
        });

      if (!selectedOptions.length) {
        return;
      }

      return `(${facet.property_path} in [${selectedOptions.join(", ")}])`;
    })
    .filter((query) => query)
    .map((facetCel) => `${facetCel}`)
    .map((query) => query)
    .join(" && ");

  return cel;
}
