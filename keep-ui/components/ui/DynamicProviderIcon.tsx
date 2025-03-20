"use client";

import React, { useState, useEffect, useCallback, memo, useRef } from "react";
import Image from "next/image";
import { useProviders } from "@/utils/hooks/useProviders";
import { useProviderImages } from "@/entities/provider-images/model/useProviderImages";

/*
If the icon is not found, it renders a default unknown icon.
*/

const fallbackIcon = "/icons/unknown-icon.png";

interface DynamicImageProviderIconProps {
  src: string;
  providerType: string;
  alt?: string;
  className?: string;
  height?: number;
  width?: number;
  title?: string;
  [key: string]: any;
}

const DynamicImageProviderIconBase = memo(
  ({ src, providerType, ...rest }: DynamicImageProviderIconProps) => {
    const initialSrc = useRef(src || fallbackIcon);
    const { data: providers } = useProviders({
      revalidateOnFocus: false,
      revalidateOnMount: false,
    });
    const { getImageUrl } = useProviderImages();
    const [imageSrc, setImageSrc] = useState<string>(initialSrc.current);
    const hasLoadedRef = useRef(false);

    const loadImage = useCallback(async () => {
      if (!providerType || !providers || hasLoadedRef.current) return;

      const isKnownProvider = providers.providers.some(
        (provider) => provider.type === providerType
      );

      if (isKnownProvider) {
        hasLoadedRef.current = true;
        return;
      }

      try {
        const customImageUrl = await getImageUrl(providerType);
        setImageSrc(customImageUrl);
      } catch (error) {
        setImageSrc(fallbackIcon);
      }
      hasLoadedRef.current = true;
    }, [providerType, providers, getImageUrl]);

    useEffect(() => {
      loadImage();
    }, [loadImage]);

    // Reset the hasLoaded flag when providerType changes
    useEffect(() => {
      hasLoadedRef.current = false;
    }, [providerType]);

    if (!providers && providerType) {
      return (
        <Image
          {...rest}
          alt={providerType || "Loading..."}
          src={initialSrc.current}
          unoptimized
        />
      );
    }

    return (
      <Image
        {...rest}
        alt={providerType || "No provider icon found"}
        src={imageSrc}
        onError={() => setImageSrc(fallbackIcon)}
        unoptimized
      />
    );
  }
);

DynamicImageProviderIconBase.displayName = "DynamicImageProviderIcon";

export const DynamicImageProviderIcon = DynamicImageProviderIconBase;
