"use client";

import React, { useState, useEffect, useCallback, memo } from "react";
import Image from "next/image";
import { useProviders } from "@/utils/hooks/useProviders";
import {
  fallbackIcon,
  useProviderImages,
} from "@/entities/provider-images/model/useProviderImages";

/*
If the icon is not found, it renders a default unknown icon.
*/

export const DynamicImageProviderIcon = (props: any) => {
  const { providerType, src, ...rest } = props;
  const { data: providers } = useProviders();
  const { getImageUrl, blobCache } = useProviderImages();
  const [imageSrc, setImageSrc] = useState<string | undefined>(
    blobCache[providerType] ?? src ?? fallbackIcon
  );

  useEffect(() => {
    if (!providerType || !providers) return;

    const loadImage = async () => {
      const isKnownProvider = providers.providers.some(
        (provider) => provider.type === providerType
      );

      if (isKnownProvider) {
        setImageSrc(`/icons/${providerType}-icon.png`);
      } else if (providerType.includes("@")) {
        // A hack so we can use the mailgun icon for alerts that comes from email (source is the sender email)
        setImageSrc("/icons/mailgun-icon.png");
      } else {
        try {
          const customImageUrl = await getImageUrl(providerType);
          setImageSrc(customImageUrl);
        } catch (error) {
          setImageSrc(fallbackIcon);
        }
      }
    };

    loadImage();
  }, [providers, getImageUrl, providerType]);

  if (!imageSrc) return;

  return (
    <Image
      {...rest}
      alt={providerType || "No provider icon found"}
      src={imageSrc}
      onError={() => setImageSrc(fallbackIcon)}
      unoptimized
    />
  );
};
