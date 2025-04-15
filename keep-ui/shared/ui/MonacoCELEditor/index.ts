"use client";

import dynamic from "next/dynamic";

const MonacoCel = dynamic(
  () => import("./MonacoCelNPM").then((mod) => mod.MonacoCelNPM),
  {
    ssr: false,
  }
);

export { MonacoCel };
