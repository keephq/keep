"use client";
import React, { useState, useEffect } from "react";
import { TableRow, TableCell } from "@tremor/react";
import Image from "next/image";
import "./provider-row.css";
import { Provider } from "@/shared/api/providers";

const ProviderRow = ({ provider }: { provider: Provider }) => {
  return (
    <>
      <TableRow className={`table-row "connected"`}>
        <TableCell className="icon-cell">
          <div className="provider-wrapper">
            <div className="icon-wrapper">
              <Image
                src={`${provider.type}.svg`}
                alt={provider.type}
                width={150}
                height={150}
                onError={(event) => {
                  const target = event.target as HTMLImageElement;
                  target.src = "/keep.svg"; // Set fallback icon
                }}
              />
            </div>
            <div className="provider-info">
              <div className="provider-name">{provider.details.name!}</div>
              <div className="provider-details">
                {Object.entries(provider.details.authentication).map(
                  ([key, value]) => (
                    <div key={key}>
                      <strong>{key}:</strong> {value}
                    </div>
                  )
                )}
              </div>
            </div>
          </div>
        </TableCell>
      </TableRow>
    </>
  );
};

export default ProviderRow;
