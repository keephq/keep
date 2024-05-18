import React, { useState } from "react";
import Image from "next/image";
import { useConfig } from "utils/hooks/useConfig";

const ImageWithFallback = (props: any) => {
  const { src, fallbackSrc, alt, width, height, className, ...rest } = props;
  const [imgSrc, setImgSrc] = useState(src);
  const { data: configData } = useConfig();

  // if not config, return null
  if (!configData) return null;


  return (
    // eslint-disable-next-line jsx-a11y/alt-text
    <Image
      {...rest}
      src={`${configData.KEEP_BASE_PATH}${imgSrc}`}
      width={width}
      height={height}
      alt={alt}
      className={className}
      // if image fails to load, set fallbackSrc
      onError={() => {
        if(fallbackSrc){
          setImgSrc(`${configData.KEEP_BASE_PATH}${fallbackSrc}`);
          return;
        }
      }}
    />
  );
};

export default ImageWithFallback;
