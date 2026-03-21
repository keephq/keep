"use client";
import { useI18n } from "@/i18n/hooks/useI18n";

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
