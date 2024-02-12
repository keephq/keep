// TODO: this needs to be refactored
import { Dialog, Transition } from "@headlessui/react";
import { Fragment, useEffect, useState } from "react";
import {
  Provider,
  ProviderMethod,
  ProviderMethodParam,
} from "app/providers/providers";
import { getSession } from "next-auth/react";
import { getApiURL } from "utils/apiUrl";
import { toast } from "react-toastify";
import Loading from "app/loading";
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
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useProviders } from "utils/hooks/useProviders";

const supportedParamTypes = ["datetime", "literal", "str"];

export function AlertMethodModal() {
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();
  const currentPreset = searchParams
    ? searchParams.get("selectedPreset")
    : "Feed";
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
  const { useAllAlertsWithSubscription } = useAlerts();
  const { data: alerts, mutate } = useAllAlertsWithSubscription();
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

  if (!isOpen || !provider || !method || !alert) {
    return <></>;
  }

  const handleClose = () => {
    setInputParameters({});
    setMethodResult(null);
    router.replace(`${pathname}?selectedPreset=${currentPreset}`);
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
    const session = await getSession();
    const apiUrl = getApiURL();

    try {
      const response = await fetch(
        `${apiUrl}/providers/${provider.id}/invoke/${method.func_name}`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${session!.accessToken}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify(userParams),
        }
      );
      const responseObject = await response.json();
      if (response.ok) {
        if (method.type === "action") mutate();
        toast.success(`Successfully called "${method.name}"`, {
          position: toast.POSITION.TOP_LEFT,
        });
        if (method.type === "view") {
          setMethodResult(responseObject);
          setIsLoading(false);
        }
      } else {
        toast.error(
          `Failed to invoke "${method.name}" on ${
            provider.details.name ?? provider.id
          } due to ${responseObject.detail}`,
          { position: toast.POSITION.TOP_LEFT }
        );
      }
    } catch (e: any) {
      toast.error(
        `Failed to invoke "${method.name}" on ${
          provider.details.name ?? provider.id
        } due to ${e.message}`,
        { position: toast.POSITION.TOP_LEFT }
      );
      handleClose();
    } finally {
      if (method.type === "action") {
        handleClose();
      }
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
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={handleClose}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-gray-900 bg-opacity-25" />
        </Transition.Child>
        <div className="fixed inset-0 overflow-y-auto">
          <div className="flex items-center justify-center p-4 text-center h-full">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 scale-95"
              enterTo="opacity-100 scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 scale-100"
              leaveTo="opacity-0 scale-95"
            >
              <Dialog.Panel
                className="w-full max-w-xl max-h-96 transform overflow-x-scroll bg-white
                                    p-6 text-left align-middle shadow-tremor transition-all rounded-xl"
              >
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
                      onClick={() =>
                        invokeMethod(provider, method, inputParameters)
                      }
                      disabled={!isInvokeEnabled()}
                    >
                      Invoke {`"${method.name}"`}
                    </Button>
                  </div>
                )}
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition>
  );
}
