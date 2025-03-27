import { PlusIcon } from "@radix-ui/react-icons";
import { Badge, Icon } from "@tremor/react";
import * as Tooltip from "@radix-ui/react-tooltip";

type GroupedByCellProps = {
  fields: string[];
};

export const GroupedByCell = ({ fields }: GroupedByCellProps) => {
  let displayedFields: any[] = fields;
  let fieldsInTooltip: any[] = [];

  if (fields.length > 2) {
    displayedFields = fields.slice(0, 1);
    fieldsInTooltip = fields.slice(1);
  }

  function renderFields(fields: string[]): JSX.Element[] | JSX.Element {
    return fields.map((group, index) => (
      <>
        <Badge color="orange" key={group}>
          {group}
        </Badge>
        {fields.length !== index + 1 && (
          <Icon icon={PlusIcon} size="xs" color="slate" />
        )}
      </>
    ));
  }

  return (
    <div className="inline-flex items-center">
      {renderFields(displayedFields)}
      {fieldsInTooltip.length > 0 && (
        <>
          <Icon icon={PlusIcon} size="xs" color="slate" />

          <Tooltip.Provider>
            <Tooltip.Root>
              <Tooltip.Trigger asChild>
                <span className="font-bold text-xs">
                  {fieldsInTooltip.length} more
                </span>
              </Tooltip.Trigger>
              <Tooltip.Portal>
                <Tooltip.Content className="TooltipContent" sideOffset={5}>
                  <div className="bg-gray-900 border-gray-200 p-2 rounded inline-flex items-center">
                    {renderFields(fieldsInTooltip)}
                  </div>
                  <Tooltip.Arrow className="TooltipArrow" />
                </Tooltip.Content>
              </Tooltip.Portal>
            </Tooltip.Root>
          </Tooltip.Provider>
        </>
      )}
    </div>
  );
};
