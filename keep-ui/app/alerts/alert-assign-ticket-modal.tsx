import React from 'react';
import Select, { components } from 'react-select';
import { Dialog } from '@headlessui/react';
import { Button, TextInput } from '@tremor/react';
import { PlusIcon } from '@heroicons/react/20/solid'
import { useForm, Controller, SubmitHandler } from 'react-hook-form';
import { Providers } from "./../providers/providers";
import { useSession } from "next-auth/react";
import { getApiURL } from 'utils/apiUrl';

interface AlertAssignTicketModalProps {
  isOpen: boolean;
  onClose: () => void;
  ticketingProviders: Providers; // Replace 'ProviderType' with the actual type of ticketingProviders
  alertFingerprint: string; // Replace 'string' with the actual type of alertFingerprint
}

interface OptionType {
  value: string;
  label: string;
  icon?: string;
  isAddProvider?: boolean;
}

interface FormData {
  provider: {
    id: string;
    value: string;
    type: string;
  };
  ticket_url: string;
}

const AlertAssignTicketModal: React.FC<AlertAssignTicketModalProps> = ({ isOpen, onClose, ticketingProviders, alertFingerprint }) => {
  const { handleSubmit, control, formState: { errors } } = useForm<FormData>();
  // get the token
  const { data: session } = useSession();

  const onSubmit: SubmitHandler<FormData> = async (data) => {
    try {
      // build the formData
      const requestData = {
        enrichments: {
          ticket_type: data.provider.type,
          ticket_url: data.ticket_url,
          ticket_provider_id: data.provider.value,
        },
        fingerprint: alertFingerprint,
      };


      const response = await fetch(`${getApiURL()}/alerts/enrich`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session?.accessToken}`,
        },
        body: JSON.stringify(requestData),
      });

      if (response.ok) {
        // Handle success
        console.log("Ticket assigned successfully");
        onClose();
      } else {
        // Handle error
        console.error("Failed to assign ticket");
      }
    } catch (error) {
      // Handle unexpected error
      console.error("An unexpected error occurred");
    }
  };

  const providerOptions: OptionType[] = ticketingProviders.map((provider) => ({
    value: provider.id,
    label: provider.details.name || '',
    type: provider.type,
  }));

  const customOptions: OptionType[] = [
    ...providerOptions,
    {
      value: 'add_provider',
      label: 'Add another ticketing provider',
      icon: 'plus',
      isAddProvider: true,
    },
  ];

  const handleOnChange = option => {
    if (option.value === 'add_provider') {
      window.open('/providers?labels=ticketing', '_blank');
    }
  };

  const Option = (props) => {
    // Check if the option is 'add_provider'
    const isAddProvider = props.data.isAddProvider;

    return (
      <components.Option {...props}>
        <div className="flex items-center">
          {isAddProvider ? (
            <PlusIcon className="h-5 w-5 text-gray-400 mr-2" />
          ) : (
            props.data.type && <img src={`/icons/${props.data.type}-icon.png`} alt="" style={{ height: '20px', marginRight: '10px' }} />
          )}
          <span style={{ color: isAddProvider ? 'gray' : 'inherit' }}>{props.data.label}</span>
        </div>
      </components.Option>
    );
  };

  const SingleValue = (props) => {
    const { children, data } = props;

    return (
      <components.SingleValue {...props}>
        <div className="flex items-center">
          {data.isAddProvider ? (
            <PlusIcon className="h-5 w-5 text-gray-400 mr-2" />
          ) : (
            data.type && <img src={`/icons/${data.type}-icon.png`} alt="" style={{ height: '20px', marginRight: '10px' }} />
          )}
          {children}
        </div>
      </components.SingleValue>
    );
  };

  return (
    <Dialog open={isOpen} onClose={onClose} className="fixed inset-0 z-10 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen px-4">
        <Dialog.Overlay className="fixed inset-0 bg-black opacity-30" />
        <div className="relative bg-white p-6 rounded-lg" style={{ width: "400px", maxWidth: "90%" }}>
          <Dialog.Title className="text-lg font-semibold">Assign Ticket</Dialog.Title>
          {ticketingProviders.length > 0 ? (
            <form onSubmit={handleSubmit(onSubmit)} className="mt-4">
              <div className="mt-4">
                <label className="block text-sm font-medium text-gray-700">Ticket Provider</label>
                <Controller
                  name="provider"
                  control={control}
                  rules={{ required: 'Provider is required' }}
                  render={({ field }) => (
                    <Select {...field} options={customOptions} onChange={(option) => { field.onChange(option); handleOnChange(option); }} components={{ Option, SingleValue }} />
                  )}
                />
              </div>
              <div className="mt-4">
                <label className="block text-sm font-medium text-gray-700">Ticket URL</label>
                <Controller
                  name="ticket_url"
                  control={control}
                  rules={{
                    required: 'URL is required',
                    pattern: {
                      value: /^(https?|http):\/\/[^\s/$.?#].[^\s]*$/i,
                      message: 'Invalid URL format',
                    },
                  }}
                  render={({ field }) => (
                    <>
                      <TextInput {...field} className="w-full mt-1" placeholder="Ticket URL" />
                      {errors.ticket_url && <span className="text-red-500">{errors.ticket_url.message}</span>}
                    </>
                  )}
                />
              </div>
              <div className="mt-6 flex gap-2">
                <Button color="orange" type="submit">Assign Ticket</Button>
                <Button onClick={onClose} variant="secondary" className="border border-orange-500 text-orange-500">Cancel</Button>
              </div>
            </form>
          ) : (
            <div className="text-center mt-4">
              <p className="text-gray-700 text-sm">
                Please connect at least one ticketing provider to use this feature.
              </p>
              <Button onClick={() => window.open('/providers?labels=ticketing', '_blank')} color="orange" className="mt-4 mr-4">
                Connect Ticketing Provider
              </Button>
              <Button onClick={onClose} variant="secondary" className="mt-4 border border-orange-500 text-orange-500">Close</Button>
            </div>
          )}
        </div>
      </div>
    </Dialog>
  );
};

export default AlertAssignTicketModal;
