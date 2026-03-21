"use client";
import { useI18n } from "@/i18n/hooks/useI18n";
import { IncidentFilterContextProvider } from "@/features/incidents/incident-list";

export default function Layout({ children }: { children: any }) {
  return (
    <IncidentFilterContextProvider>{children}</IncidentFilterContextProvider>
  );
}
