"use client";
import Image from "next/image";
import "./error.css";
import {useEffect} from "react";
import {Button, Text} from "@tremor/react";
import {useSWRConfig} from "swr";
export default function ErrorComponent({
  error,
  reset,
}: {
  error: KeepApiError
  reset: () => void
}) {
  useEffect(() => {
    // Log the error to an error reporting service
    console.error(error)
  }, [error])

  const { mutate } = useSWRConfig()

  return (
    <div className="error-container">
      <div className="error-message">{error.toString()}</div>
        <div className="error-url">
          {error.proposedResolution}
        </div>
      <div className="error-image">
        <Image src="/keep.svg" alt="Keep" width={150} height={150} />
      </div>
      <Button
          onClick={reset}
          color="orange"
          variant="secondary"
          className="mt-4 border border-orange-500 text-orange-500">
        <Text>Try Again!</Text>
      </Button>
    </div>
  )
}

// Custom Error Class
export class KeepApiError extends Error {
  url: string;
  proposedResolution: string;

  constructor(message: string, url: string, proposedResolution: string) {
    super(message);
    this.name = "KeepApiError";
    this.url = url;
    this.proposedResolution = proposedResolution;
  }
}
