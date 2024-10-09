import { Dispatch, SetStateAction } from "react";
import { TProviderLabels } from "../providers";

export interface IFilterContext {
  providersSearchString: string;
  providersSelectedTags: TProviderLabels[];
  setProvidersSearchString: Dispatch<SetStateAction<string>>;
  setProvidersSelectedTags: Dispatch<SetStateAction<TProviderLabels[]>>;
}
