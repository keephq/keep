// TODO: this needs to be refactored
import { useEffect, useState } from "react";
import {
  Provider,
  ProviderMethod,
  ProviderMethodParam,
} from "@/app/(keep)/providers/providers";
import { toast } from "react-toastify";
import Loading from "@/app/(keep)/loading";
import {
  Button,
  TextInput,
  Text,
  Select,
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

const supportedParamTypes = ["datetime", "literal", "str"];

interface AlertMethodModalProps {
  presetName: string;
  alerts: AlertDto[]
}

export function AlertMethodModal({ presetName, alerts }: AlertMethodModalProps) {
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

  useEffect(() => {
    /**
     * Auto populate params from the AlertDto
     */
    if (method && alert) {
      method.func_params?.forEach((param) => {
        const alertParamValue = (alert as any)[param.name];
        if (alertParamValue) {
          setInputParameters((prevParams) => {
            return { ...prevParams, [param.name]: alertParamValue };
          });
        }
      });
    }
  }, [alert, method]);

  if (isOpen) {
    console.log({
      provider, method, alert
    })
  }

  if (!isOpen || !provider || !method || !alert) {
    return <></>;
  }

  const handleClose = () => {
    setInputParameters({});
    setMethodResult(null);
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
          <Select
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
          </Select>
        )}
        {param.type.toLowerCase() === "str" && (
          <TextInput
            required={param.mandatory}
            placeholder={param.default ?? ""}
            value={inputParameters[param.name]}
            onValueChange={(value: string) =>
              validateAndSetParams(param.name, value, param.mandatory)
            }
          />
        )}
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
      const responseObject = await api.post(
        `/providers/${provider.id}/invoke/${method.func_name}`,
        userParams
      );
      if (method.type === "action") {
        alertsMutator();
      }
      toast.success(`Successfully called "${method.name}"`, {
        position: toast.POSITION.TOP_LEFT,
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
