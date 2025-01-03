"use client";

import { ErrorComponent } from "@/shared/ui";

export default function GlobalError({
  error,
}: {
  error: Error & { digest?: string };
}) {
  return (
    <html>
      <body>
        <ErrorComponent error={error} />
      </body>
    </html>
  );
}
