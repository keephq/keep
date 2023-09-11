import { createContext } from "react";

interface LayoutContextProps {
  searchProviderString: string;
}

export const LayoutContext = createContext<LayoutContextProps>({
  searchProviderString: "",
});
