import React from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  Button,
} from "@tremor/react";

interface SSOProvider {
  id: string;
  name: string;
  connected: boolean;
}

interface SSOTableProps {
  providers: SSOProvider[];
  onConnect: (providerId: string) => void;
  onDisconnect: (providerId: string) => void;
  isDisabled?: boolean;
}

export function SSOTable({
  providers,
  onConnect,
  onDisconnect,
  isDisabled = false,
}: SSOTableProps) {
  return (
    <Table>
      <TableHead>
        <TableRow>
          <TableHeaderCell>Provider</TableHeaderCell>
          <TableHeaderCell>Status</TableHeaderCell>
          <TableHeaderCell>Actions</TableHeaderCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {providers.map((provider) => (
          <TableRow key={provider.id}>
            <TableCell>{provider.name}</TableCell>
            <TableCell>
              {provider.connected ? "Connected" : "Not connected"}
            </TableCell>
            <TableCell>
              <Button
                style={{ marginRight: "10px" }}
                onClick={() => !isDisabled && onConnect(provider.id)}
                disabled={isDisabled}
              >
                Connect
              </Button>
              <Button
                color="orange"
                onClick={() => !isDisabled && onDisconnect(provider.id)}
                disabled={isDisabled}
              >
                Disconnect
              </Button>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
