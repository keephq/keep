"use client";

import React, { useState } from "react";
import Image from "next/image";

/*
If the icon is not found, it renders a default unknown icon.
*/
export const DynamicImageProviderIcon = (props: any) => {
  const { src, ...rest } = props;
  const [imgSrc, setImgSrc] = useState(
    src || `/icons/${props.providerType}-icon.png`
  );

  return (
    <Image
      {...rest}
      src={imgSrc}
      onError={() => {
        setImgSrc("/icons/unknown-icon.png");
      }}
    />
  );
};
