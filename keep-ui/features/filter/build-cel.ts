import { FacetDto, FacetOptionDto, FacetsConfig, FacetState } from "./models";

export function buildCel(
  facets: FacetDto[],
  facetOptions: { [key: string]: FacetOptionDto[] } | null,
  facetsState: FacetState,
  facetsConfigIdBased: FacetsConfig
): string {
  // In case facetOptions are not loaded yet, we need to create placeholder wich will be
  // populated based on uncheckedByDefaultOptionValues
  if (facetOptions == null) {
    const _facetOptions: { [key: string]: FacetOptionDto[] } = {};
    facetOptions = _facetOptions;

    facets.forEach((facet) => {
      _facetOptions[facet.id] = [];
      const facetConfig = facetsConfigIdBased?.[facet.id];
      if (facetConfig?.uncheckedByDefaultOptionValues) {
        facetConfig.uncheckedByDefaultOptionValues.forEach((optionValue) => {
          _facetOptions[facet.id].push({
            display_name: optionValue,
            value: optionValue,
            matches_count: 0,
          });
        });
      }
    });
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
