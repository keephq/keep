"use client";
import {IncidentFilterContextProvider} from "./incident-table-filters-context";

export default function Layout({ children }: { children: any }) {
  return <IncidentFilterContextProvider>{children}</IncidentFilterContextProvider>
}