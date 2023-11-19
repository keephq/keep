import { Dialog, Transition } from "@headlessui/react";
import { Fragment, useEffect, useState } from "react";
import {
  Provider,
  ProviderMethod,
  ProviderMethodParam,
} from "app/providers/providers";
import { Alert } from "./models";
import { getSession } from "utils/customAuth";
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

interface Props {
  isOpen: boolean;
  closeModal: () => void;
  method: ProviderMethod | null;
  alert: Alert;
  provider?: Provider;
  mutate?: () => void;
}

export function AlertMethodTransition({
  isOpen,
  closeModal,
  method,
  provider,
  alert,
  mutate,
}: Props) {
  const [isLoading, setIsLoading] = useState(true);
  const [autoParams, setAutoParams] = useState<{ [key: string]: string }>({});
  const [userParams, setUserParams] = useState<{ [key: string]: string }>({});
  const [results, setResults] = useState<string[] | object[] | null>(null);

  const validateAndSetUserParams = (
    key: string,
    value: string,
    mandatory: boolean
  ) => {
    const newUserParams = {
      ...userParams,
      [key]: value,
    };
    if (value === "" && mandatory) {
      delete newUserParams[key];
    }
    setUserParams(newUserParams);
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
            value={userParams[param.name] ?? ""}
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
    methodParams: { [key: string]: string },
    userParams: { [key: string]: string },
    closeModal: () => void,
    mutate?: () => void
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
          body: JSON.stringify({ ...methodParams, ...userParams }),
        }
      );
      const response_object = await response.json();
      if (response.ok) {
        if (method.type === "action") mutate!();
        toast.success(`Successfully called "${method.name}"`, {
          position: toast.POSITION.TOP_LEFT,
        });
        if (method.type === "view") {
          setResults(response_object);
          setIsLoading(false);
        }
      } else {
        toast.error(
          `Failed to invoke "${method.name}" on ${
            provider.details.name ?? provider.id
          } due to ${response_object.detail}`,
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
      closeModal();
    } finally {
      if (method.type === "action") {
        closeModal();
      }
    }
  };

  useEffect(() => {
    const newAutoParams = { ...autoParams };
    // Auto populate params from the alert itself
    method?.func_params?.forEach((param) => {
      if (Object.keys(alert).includes(param.name)) {
        newAutoParams[param.name] = alert[
          param.name as keyof typeof alert
        ] as string;
      }
    });
    if (autoParams !== newAutoParams) {
      setAutoParams(newAutoParams);
      // Invoke the method if all params are auto populated
      if (
        method?.func_params?.every((param) =>
          Object.keys(newAutoParams).includes(param.name)
        )
      ) {
        // This means all method params are auto populated
        invokeMethod(provider!, method!, newAutoParams, {}, closeModal, mutate);
      } else {
        setIsLoading(false);
      }
    }
  }, [method, alert, provider, mutate, closeModal]);

  if (!method || !provider) {
    return <></>;
  }

  const buttonEnabled = () => {
    return method.func_params
      ?.filter((fp) => fp.mandatory)
      .every((fp) =>
        Object.keys({ ...autoParams, ...userParams }).includes(fp.name)
      );
  };

  return (
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={closeModal}>
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
                ) : results ? (
                  <AlertMethodResultsTable results={results} />
                ) : (
                  <div>
                    {method.func_params?.map((param) => {
                      if (!Object.keys(autoParams).includes(param.name)) {
                        return getUserParamInput(param);
                      }
                      return <span className="hidden" key={param.name}></span>;
                    })}
                    <Button
                      type="submit"
                      color="orange"
                      onClick={() =>
                        invokeMethod(
                          provider!,
                          method!,
                          autoParams,
                          userParams,
                          closeModal,
                          mutate
                        )
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
