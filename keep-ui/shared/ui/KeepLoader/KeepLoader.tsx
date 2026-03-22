"use client";

import { Subtitle, Title } from "@tremor/react";
import clsx from "clsx";
import Image from "next/image";
import { useTranslations } from "next-intl";

export function KeepLoader({
  includeMinHeight = true,
  slowLoading = false,
  loadingText,
  className,
  ...props
}: {
  includeMinHeight?: boolean;
  slowLoading?: boolean;
  loadingText?: string;
} & React.HTMLAttributes<HTMLDivElement>) {
  const t = useTranslations("common");

  return (
    <main
      className={clsx(
        "flex flex-col items-center justify-center",
        includeMinHeight ? "min-h-screen-minus-200" : "",
        className
      )}
      {...props}
    >
      <Image
        className="animate-bounce -my-10"
        src="/keep.svg"
        alt="loading"
        width={200}
        height={200}
      />
      <Title>{loadingText ?? t("messages.loadingText")}</Title>
      {slowLoading && (
        <Subtitle>{t("messages.slowLoadingText")}</Subtitle>
      )}
    </main>
  );
}
