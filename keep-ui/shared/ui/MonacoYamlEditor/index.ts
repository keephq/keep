"use client";
import dynamic from "next/dynamic";

export const MonacoYAMLEditor = dynamic(
  () => import("./editor.client").then((mod) => mod.MonacoYAMLEditor),
  { ssr: false }
);
