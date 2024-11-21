import { createContext } from "react";

interface LayoutContextProps {
  searchProviderString: string;
  selectedTags: string[];
}

export const LayoutContext = createContext<LayoutContextProps>({
  searchProviderString: "",
  selectedTags: [],
});
