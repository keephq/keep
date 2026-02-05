"use client";
import React from "react";
import { Text, Button } from "@tremor/react";
import Image from "next/image";
import KeepPng from "../../keep.png";
import { capture } from "@/shared/lib/capture";

type KeepBannerProps = {
  bannerId: string;
  text: string | React.ReactElement<any, any>;
  newWindow: boolean;
}

const KeepBanner = ({
  bannerId,
  text,
  newWindow = false,
}: KeepBannerProps)  => {
  return (
    <div className="w-full py-2 pl-4 pr-2 mb-4 bg-orange-50 border border-orange-200 rounded-lg">
      <div className="flex items-center justify-between gap-4">
        <Image
          src={KeepPng}
          alt="Keep Logo"
          width={20}
          height={20}
          className="inline-block mr-2"
        />
        <Text className="text-sm font-medium text-black flex-grow">
          {text}
        </Text>
        <div className="flex items-center gap-2">
          <Button
            className="[&>span]:text-xs"
            onClick={() => {
              capture("star-us", {
                source: bannerId,
              });
              {newWindow ? window.open(
                "https://www.github.com/keephq/keep",
                "_blank",
                "noopener,noreferrer"
              ) : window.location.href = "https://www.github.com/keephq/keep"}
            }}
            variant="primary"
            color="orange"
            size="xs"
          >
            Give us a ⭐️
          </Button>
          <Button
            className="[&>span]:text-xs"
            onClick={() => {
              capture("talk-to-us", {
                source: bannerId,
              });
              {newWindow ? window.open(
                "https://www.keephq.dev/meet-keep",
                "_blank",
                "noopener,noreferrer"
              ) : window.location.href = "https://www.keephq.dev/meet-keep"}
            }}
            color="orange"
            variant="secondary"
            size="xs"
          >
            Talk to us
          </Button>
        </div>
      </div>
    </div>
  );
};

export default KeepBanner;
