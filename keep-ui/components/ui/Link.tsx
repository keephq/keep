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

export function Link({ icon, ...props }: LinkProps) {
  if (!icon) {
    return (
      <NextLink
        {...props}
        className={clsx(
          "text-tremor-default text-black font-semibold border-b border-tremor-brand-subtle hover:border-b-2",
          props.className
        )}
      >
        {props.children}
      </NextLink>
    );
  }

  const Icon = icon;
  const iconClassName = "size-4";
  return (
    <NextLink
      {...props}
      className={clsx(
        "group text-tremor-default text-black inline-flex gap-1 items-center transition-colors hover:text-tremor-brand",
        props.className
      )}
    >
      {props.iconPosition === "left" && <Icon className={iconClassName} />}
      <span className="transition-[border] border-b group-hover:border-b-tremor-brand/50">
        {props.children}
      </span>
      {props.iconPosition === "right" && <Icon className={iconClassName} />}
    </NextLink>
  );
}
