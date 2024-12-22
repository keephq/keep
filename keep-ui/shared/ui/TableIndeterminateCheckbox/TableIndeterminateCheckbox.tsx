// copied from https://github.com/TanStack/table/blob/main/examples/react/row-selection/src/main.tsx#L338

import clsx from "clsx";
import type { HTMLProps } from "react";
import { useEffect, useRef } from "react";

export function TableIndeterminateCheckbox({
  indeterminate,
  className = "",
  disabled = false,
  ...rest
}: { indeterminate?: boolean } & HTMLProps<HTMLInputElement>) {
  const ref = useRef<HTMLInputElement>(null!);

  useEffect(() => {
    if (typeof indeterminate === "boolean") {
      ref.current.indeterminate = !rest.checked && indeterminate;
    }
  }, [ref, indeterminate]);

  return (
    <div className="flex items-center justify-center">
      <input
        type="checkbox"
        ref={ref}
        className={clsx(
          className,
          disabled ? "cursor-not-allowed" : "cursor-pointer"
        )}
        {...rest}
      />
    </div>
  );
}
