"use client";

import React, { useState, useEffect } from "react";
import Image from "next/image";
import { useProviders } from "@/utils/hooks/useProviders";
import { useProviderImages } from "@/entities/provider-images/model/useProviderImages";

/*
If the icon is not found, it renders a default unknown icon.
*/

const fallbackIcon = "/icons/unknown-icon.png";

export const DynamicImageProviderIcon = (props: any) => {
  const { src, providerType, ...rest } = props;
  const { data: providers } = useProviders();
  const { getImageUrl } = useProviderImages();
  const [imageLoaded, setImageLoaded] = useState(false);
  const [imageSrc, setImageSrc] = useState<string>(src || fallbackIcon);

  useEffect(() => {
    const loadImage = async () => {
      if (!providers) {
        return;
      }

      if (!providerType && !imageSrc) {
        setImageSrc(src || fallbackIcon);
        setImageLoaded(true);
        return;
      }

      // Check if it's a known provider type
      const isKnownProvider = providers?.providers.some(
        (provider) => provider.type === providerType
      );

      if (isKnownProvider) {
        // do nothing
      } else {
        try {
          const customImageUrl = await getImageUrl(providerType);
          setImageSrc(customImageUrl);
        } catch (error) {
          console.error("Failed to load custom image:", error);
          setImageSrc(fallbackIcon);
        }
      }
      setImageLoaded(true);
    };

    loadImage();
  }, [providerType, providers]); // No need for cleanup since we're using the cache

  if (!providers || !imageLoaded) {
    return null;
  }

  return (
    <Image
      {...rest}
      alt={providerType || "unknƒwn provider icon"}
      src={imageSrc}
      onError={() => setImageSrc(fallbackIcon)}
      unoptimized
    />
  );
};
