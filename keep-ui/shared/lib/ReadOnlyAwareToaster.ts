import { toast } from "react-toastify";

interface configData {
  READ_ONLY: boolean;
}

export class ReadOnlyAwareToaster {
  static error(message: string, config: configData | null, toast_args: any = {}) {
    if (config?.READ_ONLY) {
      toast.warning("Changes are disabled in read-only mode. Sign up at keephq.dev to get your own instance!")
    } else {
      toast.error(message, toast_args)
    }
  }
}