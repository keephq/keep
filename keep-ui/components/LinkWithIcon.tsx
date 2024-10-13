import { AnchorHTMLAttributes, ReactNode, useState } from "react";
import Link, { LinkProps } from "next/link";
import { IconType } from "react-icons/lib";
import { Badge, Icon } from "@tremor/react";
import { usePathname } from "next/navigation";
import classNames from "classnames";
import { Trashcan } from "components/icons";

type LinkWithIconProps = {
  children: ReactNode;
  icon: IconType;
  count?: number;
  isBeta?: boolean;
  isDeletable?: boolean;
  onDelete?: () => void;
  className?: string;
  testId?: string;
} & LinkProps & AnchorHTMLAttributes<HTMLAnchorElement>;

export const LinkWithIcon = ({
  icon,
  children,
  tabIndex = 0,
  count,
  isBeta = false,
  isDeletable = false,
  onDelete,
  className,
  testId,
  ...restOfLinkProps
}: LinkWithIconProps) => {
  const pathname = usePathname();
  const [isHovered, setIsHovered] = useState(false);
  const isActive = decodeURIComponent(pathname || "") === restOfLinkProps.href?.toString();

  const iconClasses = classNames("group-hover:text-orange-400", {
    "text-orange-400": isActive,
    "text-black": !isActive,

  });

  const textClasses = classNames("truncate", {
    "text-orange-400": isActive,
    "text-black": !isActive,
  });

  const handleMouseEnter = () => setIsHovered(true);
  const handleMouseLeave = () => setIsHovered(false);

  const onClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
    if (restOfLinkProps.onClick) {
      restOfLinkProps.onClick(e);
    }
  }

  return (
    <div
      className={classNames(
        "flex items-center justify-between text-sm p-1 font-medium rounded-lg focus:ring focus:ring-orange-300 group w-full",
        {
          "bg-stone-200/50": isActive,
          "hover:bg-stone-200/50": !isActive,
        },
        className
      )}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <Link
        tabIndex={tabIndex}
        {...restOfLinkProps}
        className="flex items-center space-x-2 flex-1"
        onClick={onClick}
        data-testid={`${testId}-link`}
      >
        <Icon className={iconClasses} icon={icon} />
        <span className={textClasses}>{children}</span>
      </Link>
      <div className="flex items-center">
        {count !== undefined && count !== null && (
          <Badge
            size="xs"
            color="orange"
            data-testid={`${testId}-badge`}
          >
            {count}
          </Badge>
        )}
        {isBeta && (
          <Badge color="orange" size="xs" className="ml-2">
            Beta
          </Badge>
        )}
        {isDeletable && onDelete && (
          <button
            onClick={onDelete}
            className={`flex items-center text-slate-400 hover:text-red-500 p-0 ${
              isHovered ? 'ml-2' : ''
            }`}
          >
            <Trashcan className="text-slate-400 hover:text-red-500 group-hover:block hidden h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  );
};
