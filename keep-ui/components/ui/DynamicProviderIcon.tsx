"use client";

import React, { useState } from "react";
import Image from "next/image";

/*
If the icon is not found, it renders a default unknown icon.
*/

const fallbackIcon = "/icons/unknown-icon.png";
export const DynamicImageProviderIcon = (props: any) => {
  const { src, providerType, ...rest } = props;
  const [imageSrc, setImageSrc] = useState(
    src || `/icons/${providerType}-icon.png`
  );

  return (
    <Image
      {...rest}
      alt={providerType || "unknown provider icon"}
      src={imageSrc}
      onError={(e) => {
        setImageSrc(fallbackIcon);
      }}
    />
  );
};
