import { useEffect, useState } from "react";
import {
  Provider,
  ProviderMethod,
  ProviderMethodParam,
} from "@/shared/api/providers";
import { toast } from "react-toastify";
import Loading from "@/app/(keep)/loading";
import {
  Button,
  TextInput,
  Text,
  Select as TremorSelect,
  SelectItem,
  DatePicker,
} from "@tremor/react";
import AlertMethodResultsTable from "./alert-method-results-table";
import { useAlerts } from "utils/hooks/useAlerts";
import { useRouter, useSearchParams } from "next/navigation";
import { useProviders } from "utils/hooks/useProviders";
import Modal from "@/components/ui/Modal";
import { useApi } from "@/shared/lib/hooks/useApi";
import { showErrorToast } from "@/shared/ui";
import { AlertDto } from "@/entities/alerts/model";
import { Select } from "@/shared/ui";

const supportedParamTypes = ["datetime", "literal", "str"];

interface AlertMethodModalProps {
  presetName: string;
  alerts: AlertDto[];
}

export function AlertMethodModal({
  presetName,
  alerts,
}: AlertMethodModalProps) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const api = useApi();

  const alertFingerprint = searchParams?.get("alertFingerprint");
  const providerId = searchParams?.get("providerId");
  const methodName = searchParams?.get("methodName");
  const isOpen = !!alertFingerprint && !!providerId && !!methodName;
  const { data: providersData = { installed_providers: [] } } = useProviders(
    {}
  );
  const provider = providersData.installed_providers.find(
    (p) => p.id === providerId
  );
  const method = provider?.methods?.find((m) => m.name === methodName);
  const { alertsMutator } = useAlerts();
  const alert = alerts?.find((a) => a.fingerprint === alertFingerprint);
  const [isLoading, setIsLoading] = useState(false);
  const [inputParameters, setInputParameters] = useState<{
    [key: string]: string;
  }>({});
  const [methodResult, setMethodResult] = useState<string[] | object[] | null>(
    null
  );
  // Creating a mapping to store completions for each parameter
  const [paramCompletions, setParamCompletions] = useState<{
    [key: string]: {
      isLoading: boolean;
      completions: any[]; // Changed to any[] to accept objects with value and label
      error: Error | null;
    };
  }>({});

  useEffect(() => {
    /**
     * Auto populate params from the AlertDto and fetch completions for each parameter
     */
    if (method && alert) {
      // Auto populate params
      method.func_params?.forEach((param) => {
        const alertParamValue = (alert as any)[param.name];
        if (alertParamValue) {
          setInputParameters((prevParams) => {
            return { ...prevParams, [param.name]: alertParamValue };
          });
        }

        // Fetch completions for string parameters with auto_complete enabled
        if (param.type.toLowerCase() === "str" && param.autocomplete) {
          fetchParamCompletions(param.name);
        }
      });
    }
  }, [alert, method]);

  // Function to fetch completions for a specific parameter
  const fetchParamCompletions = async (paramName: string) => {
    if (!providerId || !method) return;

    // Set loading state for this parameter
    setParamCompletions((prev) => ({
      ...prev,
      [paramName]: { isLoading: true, completions: [], error: null },
    }));

    try {
      const url = new URL(
        `/providers/${providerId}/autocomplete/${method.func_name}`,
        window.location.origin
      );
      url.searchParams.append("paramName", paramName);
      url.searchParams.append("prefix", ""); // Empty prefix to get all available options

      const response = await api.get(url.pathname + url.search);

      // Store completions for this parameter - use response directly without mapping
      setParamCompletions((prev) => ({
        ...prev,
        [paramName]: {
          isLoading: false,
          completions: response || [], // Store the response directly
          error: null,
        },
      }));
    } catch (err) {
      console.error(`Error fetching completions for ${paramName}:`, err);
      setParamCompletions((prev) => ({
        ...prev,
        [paramName]: {
          isLoading: false,
          completions: [],
          error:
            err instanceof Error
              ? err
              : new Error("Failed to fetch completions"),
        },
      }));
    }
  };

  if (!isOpen || !provider || !method || !alert) {
    return <></>;
  }

  const handleClose = () => {
    setInputParameters({});
    setMethodResult(null);
    setParamCompletions({});
    router.replace(`/alerts/${presetName}`);
  };

  const validateAndSetParams = (
    key: string,
    value: string,
    mandatory: boolean
  ) => {
    const newUserParams = {
      ...inputParameters,
      [key]: value,
    };
    if (value === "" && mandatory) {
      delete newUserParams[key];
    }
    setInputParameters(newUserParams);
  };

  const getInputs = (param: ProviderMethodParam) => {
    if (supportedParamTypes.includes(param.type.toLowerCase()) === false) {
      return <></>;
    }

    const isAutocompleteEnabled =
      param.autocomplete && param.type.toLowerCase() === "str";

    // Get completions for this specific parameter
    const paramData = paramCompletions[param.name] || {
      isLoading: false,
      completions: [],
      error: null,
    };

    // Get the current value for this parameter as a Select option
    const currentValue = inputParameters[param.name];
    const selectValue = currentValue
      ? {
          value: currentValue,
          label: currentValue,
        }
      : null;

    return (
      <div key={param.name} className="mb-2.5">
        <Text className="capitalize mb-1">
          {param.name.replaceAll("_", " ")}
          {param.mandatory ? (
            <span className="text-red-500 font-bold">*</span>
          ) : (
            <></>
          )}
        </Text>
        {param.type.toLowerCase() === "literal" && (
          <TremorSelect
            onValueChange={(value: string) =>
              validateAndSetParams(param.name, value, param.mandatory)
            }
          >
            {param.expected_values!.map((value) => {
              return (
                <SelectItem key={value} value={value}>
                  {value}
                </SelectItem>
              );
            })}
          </TremorSelect>
        )}
        {param.type.toLowerCase() === "str" && isAutocompleteEnabled ? (
          <Select
            instanceId={`autocomplete-${param.name}`}
            options={paramData.completions} // Use completions directly, no mapping needed
            value={selectValue}
            onChange={(option: any) => {
              if (option) {
                validateAndSetParams(param.name, option.value, param.mandatory);
              }
            }}
            placeholder={param.default ?? "Select an option..."}
            isLoading={paramData.isLoading}
            isClearable
            isSearchable
            filterOption={(option, inputValue) => {
              // Allow client-side filtering for better user experience
              if (!inputValue) return true;
              return option.label
                .toLowerCase()
                .includes(inputValue.toLowerCase());
            }}
            noOptionsMessage={() => {
              if (paramData.isLoading) return "Loading...";
              if (paramData.error) return "Error fetching suggestions";
              return "No options available";
            }}
            className="w-full"
          />
        ) : param.type.toLowerCase() === "str" ? (
          <TextInput
            required={param.mandatory}
            placeholder={param.default ?? ""}
            value={inputParameters[param.name]}
            onValueChange={(value: string) =>
              validateAndSetParams(param.name, value, param.mandatory)
            }
          />
        ) : null}
        {param.type.toLowerCase() === "datetime" && (
          <DatePicker
            minDate={new Date(Date.now() + 1 * 24 * 60 * 60 * 1000)}
            defaultValue={new Date(param.default as string)}
            displayFormat="yyyy-MM-dd HH:mm:ss"
            onValueChange={(value) => {
              if (value) {
                validateAndSetParams(
                  param.name,
                  value.toISOString(),
                  param.mandatory
                );
              }
            }}
          />
        )}
      </div>
    );
  };

  const invokeMethod = async (
    provider: Provider,
    method: ProviderMethod,
    userParams: { [key: string]: string }
  ) => {
    try {
      setIsLoading(true);
      const responseObject = await api.post(
        `/providers/${provider.id}/invoke/${method.func_name}`,
        userParams
      );
      if (method.type === "action") {
        alertsMutator();
      }
      toast.success(`Successfully called "${method.name}"`, {
        position: "top-left",
      });
      if (method.type === "view") {
        setMethodResult(responseObject);
        setIsLoading(false);
      }
    } catch (e: any) {
      showErrorToast(
        e,
        `Failed to invoke "${method.name}" on ${
          provider.details.name ?? provider.id
        } due to ${e.message}`
      );
      handleClose();
    } finally {
      if (method.type === "action") {
        handleClose();
      }
      setIsLoading(false);
    }
  };

  const isInvokeEnabled = () => {
    return method.func_params
      ?.filter((fp) => fp.mandatory)
      .every((fp) =>
        Object.keys({
          ...inputParameters,
        }).includes(fp.name)
      );
  };

  return (
    <Modal isOpen={isOpen} onClose={handleClose}>
      {isLoading ? (
        <Loading includeMinHeight={false} />
      ) : methodResult ? (
        <AlertMethodResultsTable results={methodResult} />
      ) : (
        <div>
          {method.func_params?.map((param) => {
            return getInputs(param);
          })}
          <Button
            type="submit"
            color="orange"
            onClick={() => invokeMethod(provider, method, inputParameters)}
            disabled={!isInvokeEnabled()}
          >
            Invoke {`"${method.name}"`}
          </Button>
        </div>
      )}
    </Modal>
  );
}
