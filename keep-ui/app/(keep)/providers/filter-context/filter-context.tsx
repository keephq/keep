import { createContext, useState, FC, PropsWithChildren } from "react";
import { IFilterContext } from "./types";
import { useSearchParams } from "next/navigation";
import { PROVIDER_LABELS_KEYS } from "./constants";
import type { TProviderCategory, TProviderLabels } from "../providers";

export const FilterContext = createContext<IFilterContext | null>(null);

export const FilerContextProvider: FC<PropsWithChildren> = ({ children }) => {
  const searchParams = useSearchParams();

  const [providersSearchString, setProvidersSearchString] =
    useState<string>("");

  const [providersSelectedCategories, setProvidersSelectedCategories] =
    useState<TProviderCategory[]>([]);

  const [providersSelectedTags, setProvidersSelectedTags] = useState<
    TProviderLabels[]
  >(() => {
    const labels = searchParams?.get("labels");
    const labelArray = labels
      ?.split(",")
      .filter((label) => PROVIDER_LABELS_KEYS.includes(label));

    return (labelArray || []) as TProviderLabels[];
  });

  const contextValue: IFilterContext = {
    providersSearchString,
    providersSelectedTags,
    providersSelectedCategories,
    setProvidersSelectedTags,
    setProvidersSearchString,
    setProvidersSelectedCategories,
  };

  return (
    <FilterContext.Provider value={contextValue}>
      {children}
    </FilterContext.Provider>
  );
};
