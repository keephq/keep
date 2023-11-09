import { Subtitle } from "@tremor/react";
import Image from "next/image";

export default function Loading({
  includeMinHeight = true,
}: {
  includeMinHeight?: boolean;
}) {
  return (
    <main
      className={`flex flex-col items-center justify-center ${
        includeMinHeight ? "min-h-screen-minus-200" : ""
      }`}
    >
        <Image
          src="/keep_loading_new.gif"
          alt="loading"
          width={200}
          height={200}
        />
        <Subtitle>Just a second, getting your data 🚨</Subtitle>
    </main>
  );
}
