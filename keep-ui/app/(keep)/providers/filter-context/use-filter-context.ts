import { useContext } from "react";
import { FilterContext } from "./filter-context";
import { IFilterContext } from "./types";

export const useFilterContext = (): IFilterContext => {
  const filterContext = useContext(FilterContext);

  if (!filterContext) {
    throw new ReferenceError(
      "Usage of useFilterContext outside of FilterContext provider is forbidden"
    );
  }

  return filterContext;
};
