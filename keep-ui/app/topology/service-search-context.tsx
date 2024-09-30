import { createContext } from "react";

export const ServiceSearchContext = createContext<{
  serviceQuery: string;
  setServiceQuery: (query: string) => void;
  selectedServiceId: string | null;
  setSelectedServiceId: (id: string | null) => void;
}>({
  serviceQuery: "",
  setServiceQuery: (query: string) => {},
  selectedServiceId: "",
  setSelectedServiceId: (id: string | null) => {},
});
