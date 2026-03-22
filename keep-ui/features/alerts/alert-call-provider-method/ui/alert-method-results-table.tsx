import {
  Table,
  TableHead,
  TableRow,
  TableHeaderCell,
  TableBody,
  TableCell,
} from "@tremor/react";
import { useI18n } from "@/i18n/hooks/useI18n";

export default function AlertMethodResultsTable({
  results,
}: {
  results: string[] | object[];
}) {
  const { t } = useI18n();
  const resultsAreObject = results.length > 0 && typeof results[0] === "object";
  return (
    <Table>
      <TableHead>
        <TableRow>
          {!resultsAreObject ? (
            <TableHeaderCell>{t("alerts.method.results")}</TableHeaderCell>
          ) : (
            Object.keys(results[0]).map((key, index) => {
              return <TableHeaderCell key={index}>{key}</TableHeaderCell>;
            })
          )}
        </TableRow>
      </TableHead>
      <TableBody>
        {results.map((result, index) => {
          return !resultsAreObject ? (
            <TableRow key={index}>
              <TableCell>{result as string}</TableCell>
            </TableRow>
          ) : (
            <TableRow key={index}>
              {Object.values(result).map((value, index) => {
                return <TableCell key={index}>{value}</TableCell>;
              })}
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
