import React from "react";
import { Button as TremorButton, ButtonProps } from "@tremor/react";
import { cn } from "utils/helpers";

type ButtonVariantType = "destructive" | ButtonProps["variant"];

export function Button({
  variant,
  className,
  ...props
}: { variant: ButtonVariantType } & Omit<ButtonProps, "variant">) {
  let variantClasses = "";

  if (variant === "destructive") {
    variantClasses =
      "bg-red-500 hover:bg-red-600 text-white border-red-500 hover:border-red-600";
  }

  return (
    <TremorButton
      className={cn(variantClasses, className)}
      variant={variant !== "destructive" ? variant : undefined}
      {...props}
    />
  );
}
