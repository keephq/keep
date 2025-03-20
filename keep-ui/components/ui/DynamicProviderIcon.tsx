"use client";

import React, { useState, useEffect, useCallback, memo } from "react";
import Image from "next/image";
import { useProviders } from "@/utils/hooks/useProviders";
import { useProviderImages } from "@/entities/provider-images/model/useProviderImages";

/*
If the icon is not found, it renders a default unknown icon.
*/

const fallbackIcon = "/icons/unknown-icon.png";

export const DynamicImageProviderIcon = memo((props: any) => {
  const { src, providerType, ...rest } = props;
  const { data: providers } = useProviders();
  const { getImageUrl } = useProviderImages();
  const [imageSrc, setImageSrc] = useState<string>(src || fallbackIcon);

  const loadImage = useCallback(async () => {
    if (!providerType || !providers) return;

    const isKnownProvider = providers.providers.some(
      (provider) => provider.type === providerType
    );

    if (isKnownProvider) return;

    try {
      const customImageUrl = await getImageUrl(providerType);
      setImageSrc(customImageUrl);
    } catch (error) {
      setImageSrc(fallbackIcon);
    }
  }, [providers, getImageUrl]);

  useEffect(() => {
    loadImage();
  }, [loadImage]);

  if (!providers && providerType) return null;

  return (
    <Image
      {...rest}
      alt={providerType || "No provider icon found"}
      src={imageSrc}
      onError={() => setImageSrc(fallbackIcon)}
      unoptimized
    />
  );
});
