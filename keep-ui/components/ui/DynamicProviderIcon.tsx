"use client";

import React, { useState } from "react";
import Image from "next/image";

/*
If the icon is not found, it renders a default unknown icon.
*/
export const DynamicImageProviderIcon = (props: any) => {
  const { src, providerType, ...rest } = props;
  const [imgSrc, setImgSrc] = useState(
    src || `/icons/${providerType}-icon.png`
  );

  return (
    <Image
      {...rest}
      alt={providerType || "unknown provider icon"}
      src={imgSrc}
      onError={() => {
        setImgSrc("/icons/unknown-icon.png");
      }}
    />
  );
};
