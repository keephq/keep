export function getApiURL(): string {
  // https://github.com/vercel/next.js/issues/5354#issuecomment-520305040
  // https://stackoverflow.com/questions/49411796/how-do-i-detect-whether-i-am-on-server-on-client-in-next-js

  // Some background on this:
  // On docker-compose, the browser can't access the "http://keep-backend" url
  // since its the name of the container (and not accesible from the host)
  // so we need to use the "http://localhost:3000" url instead.
  const componentType = typeof window === "undefined" ? "server" : "client";

  // if its client, use the same url as the browser but with the "/backend" prefix so that middleware.ts can proxy the request to the backend
  if(componentType === "client"){
    return "/backend"
  }

  // SERVER ONLY FROM HERE ON


  // else, its the server, and we need to check if we are on vercel or not
  const gitBranchName = process.env.VERCEL_GIT_COMMIT_REF || "notvercel";
  // main branch or not vercel - use the normal url
  if(gitBranchName === "main" || gitBranchName === "notvercel"){
    return process.env.API_URL!;
  }
  // else, preview branch on vercel
  else{
    console.log("preview branch on vercel");
    let branchNameSanitized = gitBranchName.replace(/\//g, '-').substring(0, 63);
    let serviceName = `keep-api-${branchNameSanitized}`;
    if (serviceName.length > 63) {
      serviceName = serviceName.substring(0, 49);
    }

    if (serviceName.endsWith('-')) {
      serviceName = serviceName.slice(0, -1);
    }
    return process.env.API_URL!.replace('keep-api', serviceName);
  }
}
