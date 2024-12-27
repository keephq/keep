import { toast, ToastOptions } from "react-toastify";

export function showSuccessToast(message: string, options?: ToastOptions) {
  toast.success(message, options);
}
