import "@tanstack/react-table";
import { TimeFormatOption } from "@/widgets/alerts-table/lib/alert-table-time-format";

declare module "@tanstack/table-core" {
  interface ColumnMeta<TData extends RowData, TValue> {
    thClassName?: string;
    tdClassName?: string;
    sticky?: boolean;
    align?: "left" | "right" | "center";
  }

  interface TableMeta<TData extends RowData> {
    columnTimeFormats?: Record<string, TimeFormatOption>;
    setColumnTimeFormats?: (formats: Record<string, TimeFormatOption>) => void;
  }
}
