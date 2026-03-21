import { useI18n } from "@/i18n/hooks/useI18n";
import dynamic from "next/dynamic";

const IncidentCommentInput = dynamic(
  () =>
    import("./IncidentCommentInput").then((mod) => mod.IncidentCommentInput),
  {
    ssr: false,
    // mimic the quill editor while loading
    loading: () => (
      <div className="w-full h-11 px-[11px] py-[16px] leading-[1.42] text-tremor-default font-[Helvetica,Arial,sans-serif] text-[#0009] italic">
        Add a comment...
      </div>
    ),
  }
);

export { IncidentCommentInput };
