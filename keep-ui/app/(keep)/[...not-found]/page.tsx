"use client";

import { Link } from "@/components/ui";
import { Title, Button, Subtitle } from "@tremor/react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { notFound } from "next/navigation";

// https://github.com/vercel/next.js/discussions/50034
export default function NotFoundDummy() {
  notFound();
}
