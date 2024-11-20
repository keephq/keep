import { createContext, useState, FC, PropsWithChildren } from "react";
import { IFilterContext } from "./types";
import { useSearchParams } from "next/navigation";
import { PROVIDER_LABELS_KEYS } from "./constants";
import type { TProviderLabels } from "../providers";

export const FilterContext = createContext<IFilterContext | null>(null);

export const FilerContextProvider: FC<PropsWithChildren> = ({ children }) => {
  const searchParams = useSearchParams();

  const [providersSearchString, setProvidersSearchString] =
    useState<string>("");

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
    setProvidersSelectedTags,
    setProvidersSearchString,
  };

  return (
    <FilterContext.Provider value={contextValue}>
      {children}
    </FilterContext.Provider>
  );
};
