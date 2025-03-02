"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { useSupersetDashboards } from "@/utils/hooks/useSupersetDashboards";
import { EmptyStateImage } from "@/components/ui/EmptyStateImage";
import { AlertCircle } from "lucide-react";
import { KeepApiError } from "@/shared/api";

export default function OverviewPage() {
  const { dashboards, error, isLoading } = useSupersetDashboards();

  const router = useRouter();

  useEffect(() => {
    if (!isLoading && dashboards && dashboards.length > 0) {
      // Get the first dashboard (should be sorted by order already)
      const firstDashboard = dashboards[0];
      router.push(`/overview/${firstDashboard.id}`);
    }
  }, [dashboards, isLoading, router]);

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
          <span className="text-gray-600">Loading dashboards...</span>
        </div>
      </div>
    );
  }

  if (error instanceof KeepApiError) {
    return null; // Will redirect in the useEffect
  }

  if (error || !dashboards || dashboards.length === 0) {
    return (
      <div className="h-full">
        <EmptyStateImage
          message={error ? error.message : "No dashboards found"}
          documentationURL="https://docs.keephq.dev/analytics"
          imageURL="/dashboardempty.png"
          icon={AlertCircle}
          grayed={true}
          showMessage={true}
        />
      </div>
    );
  }

  // This should never render as we redirect in the useEffect
  return (
    <div className="flex items-center justify-center h-full">
      <div className="flex flex-col items-center gap-4">
        <Loader2 className="w-8 h-8 animate-spin text-orange-500" />
        <span className="text-gray-600">Redirecting to dashboard...</span>
      </div>
    </div>
  );
}
