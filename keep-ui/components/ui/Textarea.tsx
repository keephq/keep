import { Textarea as TremorTextarea, type TextareaProps } from "@tremor/react";
import { cn } from "utils/helpers";

export function Textarea({ className, ...props }: TextareaProps) {
  return (
    <TremorTextarea
      className={cn("placeholder:text-tremor-content-subtle", className)}
      {...props}
    />
  );
}
