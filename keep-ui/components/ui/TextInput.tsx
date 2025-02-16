import {
  TextInput as TremorTextInput,
  type TextInputProps,
} from "@tremor/react";
import { forwardRef } from "react";
import { cn } from "utils/helpers";

const TextInput = forwardRef(
  (
    { className, ...props }: TextInputProps,
    ref: React.Ref<HTMLInputElement>
  ) => {
    return (
      <TremorTextInput
        ref={ref}
        className={cn("[&>input]:placeholder:text-gray-400", className)}
        {...props}
      />
    );
  }
);
TextInput.displayName = "TextInput";
export { TextInput };
