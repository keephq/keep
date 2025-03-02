"use client";

import { useEffect, useState } from "react";
import { SupersetDashboard } from "../SupersetDashboard";
import { useSupersetDashboards } from "@/utils/hooks/useSupersetDashboards";
import { Loader2, AlertCircle } from "lucide-react";
import { EmptyStateImage } from "@/components/ui/EmptyStateImage";
import { KeepApiError } from "@/shared/api";
import { useRouter } from "next/navigation";

type Props = {
  params: {
    id: string;
  };
};

export default function DashboardPage({ params: { id } }: Props) {
  const { dashboards, isLoading, error } = useSupersetDashboards();
  const [dashboardId, setDashboardId] = useState<string | null>(null);
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && dashboards.length > 0) {
      // Find the dashboard with matching numeric ID
      const dashboard = dashboards.find((d) => d.id === id);
      if (dashboard) {
        setDashboardId(dashboard.id);
      }
    }
  }, [dashboards, id, isLoading]);

  useEffect(() => {
    if (error instanceof KeepApiError) {
      router.push("/incidents");
    }
  }, [error, router]);

  if (isLoading || (error && error.message === "API client not ready")) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-8 h-8 animate-spin text-orange-500" />
          <span className="text-gray-600">Loading dashboard...</span>
        </div>
      </div>
    );
  }
  if (error instanceof KeepApiError) {
    return null; // Will redirect in the useEffect
  }

  if (error || !dashboardId) {
    const showMessage = !error && !dashboardId ? true : false;
    return (
      <div className="h-full">
        <EmptyStateImage
          message={error ? error.message : "Dashboard not found"}
          documentationURL="https://docs.keephq.dev/analytics"
          imageURL="/dashboardempty.png"
          icon={AlertCircle}
          grayed={true}
          showMessage={showMessage}
        />
      </div>
    );
  }

  return (
    <div className="relative w-full h-full">
      <SupersetDashboard dashboardId={dashboardId} />
    </div>
  );
}
