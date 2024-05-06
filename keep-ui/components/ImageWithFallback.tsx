import React, { useState } from "react";
import Image from "next/image";

const ImageWithFallback = (props: any) => {
  const { src, fallbackSrc, alt, width, height, className, ...rest } = props;
  const [imgSrc, setImgSrc] = useState(src);

  return (
    // eslint-disable-next-line jsx-a11y/alt-text
    <Image
      {...rest}
      src={imgSrc}
      width={width}
      height={height}
      alt={alt}
      className={className}
      onError={() => {
        setImgSrc(fallbackSrc);
      }}
    />
  );
};

export default ImageWithFallback;
