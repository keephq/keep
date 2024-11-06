import React from "react";
import NextLink from "next/link";
import type { LinkProps as NextLinkProps } from "next/link";
import { clsx } from "clsx";

type LinkProps = {
  icon?: React.ElementType;
  iconPosition?: "left" | "right";
  children?: React.ReactNode;
} & NextLinkProps &
  React.AnchorHTMLAttributes<HTMLAnchorElement>;

export function Link({ icon, iconPosition = "left", ...props }: LinkProps) {
  if (!icon) {
    return (
      <NextLink
        {...props}
        className={clsx(
          "text-tremor-default transition-colors text-black hover:text-tremor-brand font-semibold border-b hover:border-b-tremor-brand/50",
          props.className
        )}
      >
        {props.children}
      </NextLink>
    );
  }

  const Icon = icon;
  const iconClassName = "size-4 shrink-0";
  return (
    <NextLink
      {...props}
      className={clsx(
        "group text-tremor-default text-black inline-flex gap-1 items-center transition-colors hover:text-tremor-brand",
        props.className
      )}
    >
      {iconPosition === "left" && <Icon className={iconClassName} />}
      <span className="inline-block transition-[border] border-b group-hover:border-b-tremor-brand/50">
        {props.children}
      </span>
      {iconPosition === "right" && <Icon className={iconClassName} />}
    </NextLink>
  );
}
