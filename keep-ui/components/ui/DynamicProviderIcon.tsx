"use client";

import React, { useState } from 'react';
import Image from 'next/image';


/* 
If the icon is not found, it renders a default unknown icon.
*/
export const DynamicImageProviderIcon = (props: any) => {
    const { src, ...rest } = props;
    const [imgSrc, setImgSrc] = useState(src || `/icons/${props.providerType}-icon.png`);

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

export function DynamicSVGProviderIcon({
    providerType,
    width = "24px",
    height = "24px",
    color = "none",
    ...props
}: {
    providerType: string;
    width?: string;
    height?: string;
    color?: string;
}) {
    return (
        <svg
            width={width}
            height={height}
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg"
            fill={color}
            {...props}
        >
            <DynamicImageProviderIcon
                id="image0"
                width="24"
                height="24"
                href={`/icons/${providerType}-icon.png`}
            />
        </svg>
    );
}
