"use client";
import { useState } from "react";
import { Button } from "@tremor/react";
import { useAlerts } from "@/utils/hooks/useAlerts";
import { ProviderImageUploader } from "./provider-image-uploader";
import { ProviderImagesList } from "./provider-image-list";
import { PageTitle, PageSubtitle } from "@/shared/ui";
import { PhotoIcon } from "@heroicons/react/24/outline";
import { useProviders } from "@/utils/hooks/useProviders";
import { useProviderImages } from "@/entities/provider-images/model/useProviderImages";

export default function ProviderImagesSettings() {
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const { useAllAlerts } = useAlerts();
  const { data: alerts = [] } = useAllAlerts("feed");
  const { data: providers } = useProviders();
  const { customImages } = useProviderImages();

  // Get unique provider names from alerts
  const uniqueProviders = Array.from(
    new Set(
      alerts
        .map((alert) => alert.source[0])
        .filter(
          (provider) =>
            !providers?.providers.map((p) => p.type).includes(provider)
        )
    )
  );

  const handleUploadComplete = () => {
    setIsUploadModalOpen(false);
    window.location.reload();
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <PageTitle>Provider Icons</PageTitle>
          <PageSubtitle>Customize provider icons</PageSubtitle>
        </div>
        <Button icon={PhotoIcon} onClick={() => setIsUploadModalOpen(true)}>
          Upload New Image
        </Button>
      </div>

      <ProviderImagesList />

      <ProviderImageUploader
        providers={uniqueProviders}
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        onUploadComplete={handleUploadComplete}
        customImages={customImages || []}
      />
    </div>
  );
}
