"use client";
import React from "react";
import { Text, Button } from "@tremor/react";
import Image from "next/image";
import KeepPng from "../keep.png";
import { capture } from "@/shared/lib/capture";

const ReadOnlyBanner = () => {
  return (
    <div className="w-full py-2 pl-4 pr-2 mb-4 bg-orange-50 border border-orange-200 rounded-lg">
      <div className="flex items-center justify-between gap-4">
        <Text className="text-sm font-medium text-black">
          <Image
            src={KeepPng}
            alt="Keep Logo"
            width={20}
            height={20}
            className="inline-block mr-2"
          />
          Keep is in read-only mode.
        </Text>
        <div className="flex items-center gap-2">
          <Button
            className="[&>span]:text-xs"
            onClick={() => {
              capture("try-keep-for-free", {
                source: "read-only-banner",
              });
              window.open(
                "https://platform.keephq.dev/providers",
                "_blank",
                "noopener,noreferrer"
              );
            }}
            variant="primary"
            color="orange"
            size="xs"
          >
            Try for free
          </Button>
          <Button
            className="[&>span]:text-xs"
            onClick={() => {
              capture("talk-to-us", {
                source: "read-only-banner",
              });
              window.open(
                "https://www.keephq.dev/meet-keep",
                "_blank",
                "noopener,noreferrer"
              );
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

export default ReadOnlyBanner;
