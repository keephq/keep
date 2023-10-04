import {
  Accordion,
  AccordionHeader,
  AccordionBody,
  Badge,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  Icon,
} from "@tremor/react";
import { Provider } from "./providers";
import { QuestionMarkCircleIcon } from "@heroicons/react/24/outline";

const ProviderFormScopes = ({
  provider,
  validatedScopes,
}: {
  provider: Provider;
  validatedScopes: { [key: string]: string | boolean };
}) => {
  return (
    <Accordion className="mb-5" defaultOpen={true}>
      <AccordionHeader>Scopes</AccordionHeader>
      <AccordionBody>
        <Table className="mt-5">
          <TableHead>
            <TableRow>
              <TableHeaderCell>Name</TableHeaderCell>
              <TableHeaderCell>Last Status</TableHeaderCell>
              <TableHeaderCell>Description</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {
              // provider.scopes! is because we validates scopes exists in the parent component
              provider.scopes!.map((scope) => {
                return (
                  <TableRow key={scope.name}>
                    <TableCell>
                      {scope.name}
                      {scope.mandatory ? (
                        <span className="text-red-400">*</span>
                      ) : null}
                      {scope.mandatory_for_webhook ? (
                        <span className="text-orange-300">*</span>
                      ) : null}
                    </TableCell>
                    <TableCell>
                      <Badge
                        color={
                          validatedScopes[scope.name] === true // scope is tested and valid
                            ? "emerald"
                            : validatedScopes[scope.name] === undefined // scope was not tested
                            ? "gray"
                            : "red" // scope was tested and is a string, meaning it has an error
                        }
                      >
                        {validatedScopes[scope.name] === true
                          ? "Valid"
                          : validatedScopes[scope.name] === undefined
                          ? "Not checked"
                          : validatedScopes[scope.name]}
                      </Badge>
                    </TableCell>
                    <TableCell
                      title={scope.description}
                      className="max-w-xs truncate"
                    >
                        <div className="flex items-center">
                      {scope.description}
                      {scope.mandatory_for_webhook ? (
                        <Icon
                        icon={QuestionMarkCircleIcon}
                        variant="simple"
                        color="gray"
                        size="sm"
                        tooltip="Mandatory for webhook installation"
                      />
                      ) : null}
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })
            }
          </TableBody>
        </Table>
      </AccordionBody>
    </Accordion>
  );
};

export default ProviderFormScopes;
