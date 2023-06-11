import React, { useState, useEffect } from "react";
import { TableRow, TableCell } from "@tremor/react";
import Image from "next/image";
import "./providers.css";
import ProviderForm from "./provider-form";
import { Provider } from "./providers";

const ProviderRow = ({ provider }: { provider: Provider }) => {
  const [expanded, setExpanded] = useState(false);
  const [formData, setFormData] = useState({});

  const handleExpand = () => {
    setExpanded(!expanded);
  };

  const onFormChange = (formValues: any) => {
    setFormData(formValues);
  };

  // Update formData with authentication data
  useEffect(() => {
    if (provider.installed) {
      const authenticationData = Object.keys(
        provider.details.authentication
      ).reduce((data, name) => {
        const value = provider.details.authentication[name] || "";
        return { ...data, [name]: value };
      }, {});
      setFormData(authenticationData);
    }
  }, [provider.installed, provider.details]);

  const isComingSoonProvider = provider.comingSoon || false;
  return (
    <>
      <TableRow
        className={`table-row ${provider.installed ? "connected" : ""} ${
          isComingSoonProvider ? "coming-soon" : ""
        }`}
      >
        <TableCell className="icon-cell">
          <div className="icon-wrapper">
            <Image
              src={`${provider.id}.svg`}
              alt={provider.id}
              width={150}
              height={150}
              onError={(event) => {
                const target = event.target as HTMLImageElement;
                target.src = "keep.svg"; // Set fallback icon
              }}
            />
          </div>
          <div className="provider-info">
            <div className="provider-name">{provider.id.charAt(0).toUpperCase() + provider.id.slice(1)}</div>
          </div>
        </TableCell>
        <TableCell className="expand-cell">
          {isComingSoonProvider ? (
            <div className="coming-soon-label">Coming Soon 🚧</div>
          ) : (
            <div className="expand-button-container">
              <button
                type="button"
                className="expand-button"
                onClick={handleExpand}
              >
                {expanded
                  ? "Collapse"
                  : provider.installed
                  ? "Expand"
                  : "Connect"}
              </button>
            </div>
          )}
        </TableCell>
      </TableRow>
      {expanded && (
        <TableRow>
          <TableCell colSpan={2}>
            <div className="expanded-content">
              <ProviderForm
                provider={provider}
                formData={formData}
                onFormChange={onFormChange}
              />
            </div>
          </TableCell>
        </TableRow>
      )}
    </>
  );
};

export default ProviderRow;
