import React from "react";
import Image from "next/image";
import "./logo-error.css";

export interface KeepLogoErrorProps {
  width?: number;
  height?: number;
}

export const KeepLogoError = ({
  width = 200,
  height = 200,
}: KeepLogoErrorProps) => {
  return (
    <div className="wrapper -my-10" style={{ width, height }}>
      <div className="logo-container">
        <svg width="100%" height="100%" viewBox="0 0 200 200">
          <defs>
            <filter id="tvNoise">
              <feTurbulence
                type="fractalNoise"
                baseFrequency="0.1"
                numOctaves="4"
                seed="1"
                stitchTiles="stitch"
              >
                <animate
                  attributeName="seed"
                  from="1"
                  to="10"
                  dur="0.1s"
                  repeatCount="indefinite"
                />
              </feTurbulence>
              <feDisplacementMap in="SourceGraphic" scale="5" />
            </filter>

            <filter id="redChannel">
              <feColorMatrix
                type="matrix"
                values="1.5 0 0 0 0.2  0 0 0 0 0  0 0 0 0 0  0 0 0 0.8 0"
              />
              <feOffset dx="0" dy="0">
                <animate
                  attributeName="dx"
                  values="0;-10;0"
                  dur="4s"
                  keyTimes="0;0.96;1"
                  repeatCount="indefinite"
                />
              </feOffset>
            </filter>

            <filter id="greenChannel">
              <feColorMatrix
                type="matrix"
                values="0 0 0 0 0  0 1.5 0 0 0.2  0 0 0 0 0  0 0 0 0.8 0"
              />
              <feOffset dx="0" dy="0">
                <animate
                  attributeName="dx"
                  values="0;5;0"
                  dur="4s"
                  keyTimes="0;0.96;1"
                  repeatCount="indefinite"
                />
                <animate
                  attributeName="dy"
                  values="0;-8;0"
                  dur="4s"
                  keyTimes="0;0.96;1"
                  repeatCount="indefinite"
                />
              </feOffset>
            </filter>
          </defs>

          <g style={{ mixBlendMode: "screen" }}>
            <foreignObject
              width="100%"
              height="100%"
              style={{ filter: "url(#redChannel)" }}
            >
              <div>
                <Image
                  src="/keep.svg"
                  alt="Keep Logo"
                  width={width}
                  height={height}
                  className="w-full h-full"
                />
              </div>
            </foreignObject>
            <foreignObject
              width="100%"
              height="100%"
              style={{ filter: "url(#greenChannel)" }}
            >
              <div>
                <Image
                  src="/keep.svg"
                  alt="Keep Logo"
                  width={width}
                  height={height}
                  className="w-full h-full"
                />
              </div>
            </foreignObject>
            <foreignObject
              width="100%"
              height="100%"
              style={{ filter: "url(#tvNoise)" }}
            >
              <div>
                <Image
                  src="/keep.svg"
                  alt="Keep Logo"
                  width={width}
                  height={height}
                  className="w-full h-full"
                />
              </div>
            </foreignObject>
          </g>
        </svg>
      </div>
    </div>
  );
};
