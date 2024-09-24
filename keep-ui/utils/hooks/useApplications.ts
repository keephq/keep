import { useLocalStorage } from "utils/hooks/useLocalStorage";
import { v4 as uuidv4 } from "uuid";
import { Application } from "../../app/topology/models";

// Mocked API
// TODO: replace with actual API
export function useApplications() {
  const [applications, setApplications] = useLocalStorage<Application[]>(
    "applications",
    []
  );

  function addApplication(
    application: Omit<Application, "id"> & { id?: string }
  ) {
    const id = application.id ?? uuidv4();
    setApplications([...applications, { ...application, id }]);
  }

  function removeApplication(applicationId: string) {
    setApplications(applications.filter((app) => app.id !== applicationId));
  }

  function updateApplication(application: Application) {
    setApplications(
      applications.map((app) => (app.id === application.id ? application : app))
    );
  }

  return { applications, addApplication, removeApplication, updateApplication };
}
