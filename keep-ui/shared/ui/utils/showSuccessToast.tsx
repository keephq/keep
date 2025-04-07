import {
  toast,
  ToastContent,
  ToastOptions,
  ToastPosition,
} from "react-toastify";

export function showSuccessToast(
  message: ToastContent,
  options: ToastOptions = {
    position:
      (process.env.PUBLIC_DEFAULT_TOAST_POSITION as ToastPosition) ??
      "top-left",
  }
) {
  toast.success(message, options);
}
