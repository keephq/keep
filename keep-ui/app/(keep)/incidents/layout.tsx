"use client";
import { IncidentFilterContextProvider } from "@/features/incidents/incident-list";

export default function Layout({ children }: { children: any }) {
  return (
    <IncidentFilterContextProvider>{children}</IncidentFilterContextProvider>
  );
}
