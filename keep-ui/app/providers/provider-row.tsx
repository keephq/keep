import React, { useState, useEffect } from 'react';
import { TableRow, TableCell } from '@tremor/react';
import './providers.css';
import ProviderForm from './provider-form';

type AuthenticationMethod = {
  name: string;
  desc: string;
  type: string;
  placeholder?: string;
  validation?: (value: string) => boolean;
};

export type Provider = {
  id: string;
  name: string;
  authentication: AuthenticationMethod[];
  icon: string;
  connected: boolean;
};

type ProviderRowProps = {
  provider: Provider;
};

const ProviderRow = ({ provider }: ProviderRowProps) => {
  const [expanded, setExpanded] = useState(false);
  const [formData, setFormData] = useState({});

  const handleExpand = () => {
    setExpanded(!expanded);
  };

  const onFormChange = (formValues) => {
    setFormData(formValues);
  };

  // Update formData with authentication data
  useEffect(() => {
    if (provider.connected) {
      const authenticationData = provider.authentication.reduce((data, method) => {
        const { name } = method;
        const value = method.value || '';
        return { ...data, [name]: value };
      }, {});
      setFormData(authenticationData);
    }
  }, [provider.connected]);

  return (
    <>
      <TableRow className={`table-row ${provider.connected ? 'connected' : ''}`}>
        <TableCell className="icon-cell">
          <div className="icon-wrapper">
            <img src={provider.icon} alt={provider.name} />
          </div>
          <div className="provider-info">
            <div className="provider-name">{provider.name}</div>
          </div>
        </TableCell>
        <TableCell className="expand-cell">
          <div className="expand-button-container">
            <button type="button" className="expand-button" onClick={handleExpand}>
              {expanded ? 'Collapse' : provider.connected ? 'Disconnect' : 'Connect'}
            </button>
          </div>
        </TableCell>
      </TableRow>
      {expanded && (
        <TableRow>
          <TableCell colSpan={2}>
            <div className="expanded-content">
              <ProviderForm provider={provider} formData={formData} onFormChange={onFormChange} />
            </div>
          </TableCell>
        </TableRow>
      )}
    </>
  );
};

export default ProviderRow;
