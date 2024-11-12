"use client";

export default function SentryExamplePage() {
  return (
    <button
      type="button"
      onClick={() => {
        throw new Error("Sentry Frontend Error");
      }}
    >
      Throw error
    </button>
  );
}
