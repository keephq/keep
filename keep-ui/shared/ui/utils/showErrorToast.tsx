import { Link } from "@/components/ui";
import { KeepApiError, KeepApiReadOnlyError } from "@/shared/api";
import { toast, ToastOptions } from "react-toastify";

export function showErrorToast(
  error: unknown,
  customMessage?: React.ReactNode,
  options?: ToastOptions
) {
  if (error instanceof KeepApiReadOnlyError) {
    toast.warning(
      <>
        You&apos;re in read-only mode. Sign up at{" "}
        <Link
          href="https://keephq.dev"
          target="_blank"
          rel="noreferrer noopener"
        >
          keephq.dev
        </Link>{" "}
        to get your own instance!
      </>,
      options
    );
  } else if (error instanceof KeepApiError) {
    toast.error(customMessage || error.message, options);
  } else {
    toast.error(
      customMessage ||
        (error instanceof Error ? error.message : "Unknown error"),
      options
    );
  }
}
