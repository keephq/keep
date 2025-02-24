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
  Button,
} from "@tremor/react";
import { Provider } from "@/shared/api/providers";
import {
  ArrowPathIcon,
  QuestionMarkCircleIcon,
} from "@heroicons/react/24/outline";
import "./provider-form-scopes.css";

const ProviderFormScopes = ({
  provider,
  validatedScopes,
  refreshLoading,
  onRevalidate,
}: {
  provider: Provider;
  validatedScopes: { [key: string]: string | boolean };
  refreshLoading: boolean;
  onRevalidate: () => void;
}) => {
  return (
    <Accordion className="mb-5" defaultOpen={true}>
      <AccordionHeader>Scopes</AccordionHeader>
      <AccordionBody className="overflow-hidden">
        {provider.installed && (
          <Button
            color="gray"
            size="xs"
            icon={ArrowPathIcon}
            onClick={onRevalidate}
            variant="secondary"
            loading={refreshLoading}
          >
            Refresh
          </Button>
        )}
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
                let isScopeString =
                  typeof validatedScopes[scope.name] === "string";
                let isScopeLong = false;

                if (isScopeString) {
                  isScopeLong =
                    validatedScopes[scope.name].toString().length > 100;
                }
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
                    <TableCell id="scope-badge">
                      <Badge
                        color={
                          validatedScopes[scope.name] === true // scope is tested and valid
                            ? "emerald"
                            : validatedScopes[scope.name] === undefined // scope was not tested
                              ? "gray"
                              : "red" // scope was tested and is a string, meaning it has an error
                        }
                        className={`truncate ${isScopeLong ? "max-w-lg" : "max-w-xs"}`}
                      >
                        {validatedScopes[scope.name] === true
                          ? "Valid"
                          : validatedScopes[scope.name] === undefined
                            ? "Not checked"
                            : validatedScopes[scope.name]}
                      </Badge>
                    </TableCell>
                    <TableCell title={scope.description} className="max-w-xs">
                      <div className="flex items-center break-words whitespace-normal">
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
