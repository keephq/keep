"use client";
import { useState } from "react";
import { Card, Button } from "@tremor/react";
import { useAlerts } from "@/utils/hooks/useAlerts";
import { ProviderImageUploader } from "./provider-image-uploader";
import { ProviderImagesList } from "./provider-image-list";
import { PageTitle, PageSubtitle } from "@/shared/ui";
import { PhotoIcon } from "@heroicons/react/24/outline";

export default function ProviderImagesSettings() {
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const { useAllAlerts } = useAlerts();
  const { data: alerts = [] } = useAllAlerts("feed");

  // Get unique provider names from alerts
  const uniqueProviders = Array.from(
    new Set(alerts.map((alert) => alert.source[0]))
  );

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <PageTitle>Provider Images</PageTitle>
          <PageSubtitle>Customize provider icons</PageSubtitle>
        </div>
        <Button icon={PhotoIcon} onClick={() => setIsUploadModalOpen(true)}>
          Upload New Image
        </Button>
      </div>

      <ProviderImagesList
        onSelectProvider={(provider) => {
          // Handle edit of existing image
        }}
      />

      <ProviderImageUploader
        providers={uniqueProviders}
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        customImages={[]} // This will be populated from the ProviderImagesList component
      />
    </div>
  );
}
