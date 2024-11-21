"use client";

import { notFound } from "next/navigation";

// https://github.com/vercel/next.js/discussions/50034
export default function NotFoundDummy() {
  notFound();
}
