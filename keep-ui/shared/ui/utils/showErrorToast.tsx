import { Link } from "@/components/ui";
import { KeepApiError, KeepApiReadOnlyError } from "@/shared/api";
import { toast, ToastOptions, ToastPosition } from "react-toastify";

const DEFAULT_TOAST_OPTIONS: ToastOptions = {
  position:
    (process.env.PUBLIC_DEFAULT_TOAST_POSITION as ToastPosition) ?? "top-left",
};

export function showErrorToast(
  error: unknown,
  messageOverride?: React.ReactNode,
  options: ToastOptions & {
    messagePrefix?: string;
  } = {
    messagePrefix: "",
    ...DEFAULT_TOAST_OPTIONS,
  }
) {
  const { messagePrefix, ...toastOptions } = {
    ...DEFAULT_TOAST_OPTIONS,
    ...options,
  };
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
      toastOptions
    );
  } else if (error instanceof KeepApiError) {
    toast.error(
      messageOverride ||
        [messagePrefix, error.message, error.proposedResolution]
          .filter(Boolean)
          .join(". "),
      toastOptions
    );
  } else {
    // Console error for debugging unknown errors
    console.error("Unknown error:", error);
    toast.error(
      messageOverride ||
        [
          messagePrefix,
          error instanceof Error ? error.message : "Unknown error",
        ]
          .filter(Boolean)
          .join(". "),
      toastOptions
    );
  }
}
