"use client";
import React from "react";
import { X } from "lucide-react";
import { useLocalStorage } from "utils/hooks/useLocalStorage";
import { Card, Text, Button } from "@tremor/react";
import Image from "next/image";
import KeepPng from "../keep.png";

const ReadOnlyBanner = () => {
  const [isVisible, setIsVisible] = useLocalStorage(
    "read-only-banner-visible",
    true
  );

  if (!isVisible) return null;

  return (
    <Card
      className="w-full rounded-none bg-orange-400 text-black py-2"
      decoration="none"
    >
      <div className="container mx-auto relative">
        <div className="flex items-center justify-center gap-2">
          <Image src={KeepPng} alt="Keep Logo" width={20} height={20} />
          <Text className="text-sm font-medium text-black">
            Keep is in read-only mode.
          </Text>
        </div>
        <Button
          onClick={() => setIsVisible(false)}
          variant="light"
          color="gray"
          icon={X}
          size="xs"
          className="hover:text-gray-500 transition-colors absolute right-0 top-1/2 -translate-y-1/2"
        />
      </div>
    </Card>
  );
};

export default ReadOnlyBanner;
