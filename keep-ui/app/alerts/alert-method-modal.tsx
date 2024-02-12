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
import { useSearchParams } from "next/navigation";
import { useProviders } from "utils/hooks/useProviders";

export function AlertMethodModal() {
  const searchParams = useSearchParams();
  const alertFingerprint = searchParams?.get("alertFingerprint");
  const providerId = searchParams?.get("providerId");
  const methodName = searchParams?.get("methodName");
  const isOpen = !!alertFingerprint && !!providerId && !!methodName;

  const [isLoading, setIsLoading] = useState(true);
  const [userInputParameters, setUserInputParameters] = useState<{
    [key: string]: string;
  }>({});
  const [methodResult, setMethodResult] = useState<string[] | object[] | null>(
    null
  );

  const { data: providersData = { installed_providers: [] } } = useProviders(
    {}
  );
  const { useAllAlertsWithSubscription } = useAlerts();
  const { data: alerts, mutate } = useAllAlertsWithSubscription();

  if (!isOpen) {
    return <></>;
  }

  const providerMethods = providersData.installed_providers.find(
    (p) => p.id === providerId
  )?.methods;
  if (!providerMethods) return <></>;

  const method = providerMethods.find((m) => m.name === methodName);
  if (!method) return <></>;

  const alert = alerts?.find((a) => a.fingerprint === alertFingerprint);
  if (!alert) return <></>;

  const handleClose = () => {};

  const validateAndSetUserParams = (
    key: string,
    value: string,
    mandatory: boolean
  ) => {
    const newUserParams = {
      ...userInputParameters,
      [key]: value,
    };
    if (value === "" && mandatory) {
      delete newUserParams[key];
    }
    setUserInputParameters(newUserParams);
  };

  const getUserParamInput = (param: ProviderMethodParam) => {
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
              validateAndSetUserParams(param.name, value, param.mandatory)
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
            value={userInputParameters[param.name] ?? ""}
            onValueChange={(value: string) =>
              validateAndSetUserParams(param.name, value, param.mandatory)
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
                validateAndSetUserParams(
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

  if (!method || !provider) {
    return <></>;
  }

  const buttonEnabled = () => {
    return method.func_params
      ?.filter((fp) => fp.mandatory)
      .every((fp) =>
        Object.keys({
          ...userInputParameters,
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
          <div className="flex items-center justify-center p-4 text-center  h-full">
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
                className="w-full max-w-lg max-h-96 transform overflow-scroll bg-white
                                    p-6 text-left align-middle shadow-tremor transition-all rounded-xl"
              >
                {isLoading ? (
                  <Loading includeMinHeight={false} />
                ) : methodResult ? (
                  <AlertMethodResultsTable results={methodResult} />
                ) : (
                  <div>
                    {method.func_params?.map((param) => {
                      return getUserParamInput(param);
                    })}
                    <Button
                      type="submit"
                      color="orange"
                      onClick={() =>
                        invokeMethod(provider, method, userInputParameters)
                      }
                      disabled={!buttonEnabled()}
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
