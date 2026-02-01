import React from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  Text,
  Button,
  Badge,
} from "@tremor/react";
import { TrashIcon, KeyIcon } from "@heroicons/react/24/outline";
import { UpdateIcon } from "@radix-ui/react-icons";
import { CopyBlock, a11yLight } from "react-code-blocks";

interface APIKey {
  reference_id: string;
  secret: string;
  role: string;
  created_by: string;
  created_at: string;
  last_used: string | null;
}

interface APIKeysTableProps {
  apiKeys: APIKey[];
  onRegenerate: (apiKeyId: string, event: React.MouseEvent) => void;
  onDelete: (apiKeyId: string, event: React.MouseEvent) => void;
  isDisabled?: boolean;
}

export function APIKeysTable({
  apiKeys,
  onRegenerate,
  onDelete,
  isDisabled = false,
}: APIKeysTableProps) {
  const getCopyBlockProps = (secret: string) => ({
    theme: { ...a11yLight },
    language: "text",
    text: secret,
    codeBlock: true,
    showLineNumbers: false,
  });

  return (
    <Table>
      <TableHead>
        <TableRow>
          <TableHeaderCell className="text-left">Name</TableHeaderCell>
          <TableHeaderCell className="text-left w-1/4">Key</TableHeaderCell>
          <TableHeaderCell className="text-left">Role</TableHeaderCell>
          <TableHeaderCell className="text-left">Created By</TableHeaderCell>
          <TableHeaderCell className="text-left">Created At</TableHeaderCell>
          <TableHeaderCell className="text-left">Last Used</TableHeaderCell>
          <TableHeaderCell className="w-1/12"></TableHeaderCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {apiKeys.map((key) => (
          <TableRow
            key={key.reference_id}
            className="hover:bg-gray-50 transition-colors duration-200 cursor-pointer group"
          >
            <TableCell>{key.reference_id}</TableCell>
            <TableCell className="text-left">
              <CopyBlock {...getCopyBlockProps(key.secret)} />
            </TableCell>
            <TableCell className="text-left">
              <Badge color="orange">{key.role || "N/A"}</Badge>
            </TableCell>
            <TableCell className="text-left">
              <Text>{key.created_by}</Text>
            </TableCell>
            <TableCell className="text-left">
              <Text>{key.created_at}</Text>
            </TableCell>
            <TableCell className="text-left">
              <Text>{key.last_used ?? "Never"}</Text>
            </TableCell>
            <TableCell className="w-1/12">
              <div className="flex justify-end space-x-2 opacity-0 group-hover:opacity-100 transition-opacity">
                <Button
                  tooltip="Regenerate key"
                  icon={UpdateIcon}
                  variant="light"
                  color="orange"
                  onClick={(e) =>
                    !isDisabled && onRegenerate(key.reference_id, e)
                  }
                  disabled={isDisabled}
                />
                <Button
                  tooltip="Delete key"
                  icon={TrashIcon}
                  variant="light"
                  color="orange"
                  onClick={(e) => !isDisabled && onDelete(key.reference_id, e)}
                  disabled={isDisabled}
                />
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
