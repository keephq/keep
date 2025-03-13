"use client";
import dynamic from "next/dynamic";

export const YamlEditor = dynamic(
  () => import("./editor.client").then((mod) => mod.YamlEditor),
  { ssr: false }
);
