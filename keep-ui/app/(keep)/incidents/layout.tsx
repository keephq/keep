"use client";
import { IncidentFilterContextProvider } from "../../../features/incident-list/ui/incident-table-filters-context";

export default function Layout({ children }: { children: any }) {
  return (
    <IncidentFilterContextProvider>{children}</IncidentFilterContextProvider>
  );
}
