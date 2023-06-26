"use client";
import Image from "next/image";
import "./error.css";

// Custom Error Component
export default function ErrorComponent({
  errorMessage,
  url,
}: {
  errorMessage: String;
  url: String;
}) {
  return (
    <div className="error-container">
      <div className="error-message">{errorMessage}</div>
      {url && (
        <div className="error-url">
          Failed to query {url}, is Keep API up?
        </div>
      )}
      <div className="error-image">
        <Image src="/keep.svg" alt="Keep" width={150} height={150} />
      </div>
    </div>
  );
}

export class KeepApiError extends Error {
  url: string;

  constructor(message: string, url: string) {
    super(message);
    this.name = "KeepApiError";
    this.url = url;
  }
}
