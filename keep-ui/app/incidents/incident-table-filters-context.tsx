import {Dispatch, SetStateAction, useCallback, useContext, useEffect} from 'react';

import { createContext, useState, FC, PropsWithChildren } from "react";
import { useSearchParams, useRouter, usePathname } from "next/navigation";
import {useIncidentsMeta} from "../../utils/hooks/useIncidents";
import {IncidentsMetaDto} from "./models";

interface IIncidentFilterContext {
  meta: IncidentsMetaDto | undefined;

  statuses: string[];
  severities: string[];
  assignees: string[];
  services: string[];
  sources: string[];

  setStatuses: (value: string[]) => void;
  setSeverities: (value: string[]) => void;
  setAssignees: (value: string[]) => void;
  setServices: (value: string[]) => void;
  setSources: (value: string[]) => void;
}

const IncidentFilterContext = createContext<IIncidentFilterContext | null>(null);

export const IncidentFilterContextProvider: FC<PropsWithChildren> = ({ children }) => {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const {data: incidentsMeta, isLoading} = useIncidentsMeta();

  const setFilterValue = (filterName: string) => {
    return () => {
     if (incidentsMeta === undefined) return [];

      const values = searchParams?.get(filterName);
      const valuesArray = values?.split(',').filter(
        value => incidentsMeta[filterName as keyof IncidentsMetaDto]?.includes(value)
      );

      return (valuesArray || []) as string[];
    }
  }

  const [statuses, setStatuses] = useState<string[]>(setFilterValue("statuses"));
  const [severities, setSeverities] = useState<string[]>(setFilterValue("severities"));
  const [assignees, setAssignees] = useState<string[]>(setFilterValue("assignees"));
  const [services, setServices] = useState<string[]>(setFilterValue("services"));
  const [sources, setSources] = useState<string[]>(setFilterValue("sources"));

  useEffect(() => {
    if (!isLoading) {
      setStatuses(setFilterValue("statuses"));
      setSeverities(setFilterValue("severities"));
      setAssignees(setFilterValue("assignees"));
      setServices(setFilterValue("services"));
      setSources(setFilterValue("sources"));
    }
  }, [isLoading])

  const createQueryString = useCallback(
    (name: string, value: string[]) => {
      const params = new URLSearchParams(searchParams?.toString())
      if (value.length == 0) {
        params.delete(name);
      } else {
        params.set(name, value.join(","));
      }


      return params.toString();
    },
    [searchParams]
  )

  const filterSetter = (filterName: string, stateSetter: Dispatch<SetStateAction<string[]>>) => {
    return (value: string[]) => {
      router.push(pathname + '?' + createQueryString(filterName, value));
      stateSetter(value);
    }
  }

  const contextValue: IIncidentFilterContext = {
    meta: incidentsMeta,
    statuses,
    severities,
    assignees,
    services,
    sources,

    setStatuses: filterSetter("statuses", setStatuses),
    setSeverities: filterSetter("severities", setSeverities),
    setAssignees: filterSetter("assignees", setAssignees),
    setServices: filterSetter("services", setServices),
    setSources: filterSetter("sources", setSources),
  }

  return <IncidentFilterContext.Provider value={contextValue}>{children}</IncidentFilterContext.Provider>
}

export const useIncidentFilterContext = (): IIncidentFilterContext => {
  const filterContext  = useContext(IncidentFilterContext);

  if (!filterContext) {
    throw new ReferenceError('Usage of useIncidentFilterContext outside of IncidentFilterContext provider is forbidden');
  }

  return filterContext;
}