export function getApiURL(): string {
  // https://github.com/vercel/next.js/issues/5354#issuecomment-520305040
  // https://stackoverflow.com/questions/49411796/how-do-i-detect-whether-i-am-on-server-on-client-in-next-js

  // Some background on this:
  // On docker-compose, the browser can't access the "http://keep-backend" url
  // since its the name of the container (and not accesible from the host)
  // so we need to use the "http://localhost:3000" url instead.
  const componentType = typeof window === "undefined" ? "server" : "client";
  let apiUrl = "";
  if (componentType === "server") {
    apiUrl = process.env.API_URL!;
  } else {
    apiUrl =  process.env.NEXT_PUBLIC_API_URL!;
  }

  // If Keep UI is deployed on Vercel and Keep API deployed in Cloud Run, we need
  // somehow to tell Keep UI where to find the API. We can do this by using
  // https://vercel.com/docs/concepts/projects/environment-variables/system-environment-variables
  // TODO: add documentation about how to set this up for OSS users
  if(process.env.VERCEL_GIT_COMMIT_REF){
    const branchName = process.env.VERCEL_GIT_COMMIT_REF;
    let sanitizedBranchName = branchName.replace(/\//g, '-');
    if (sanitizedBranchName.length > 63) {
        sanitizedBranchName = sanitizedBranchName.substring(0, 63);
    }
    // If branch name is not 'main', append it to the API URL
    if (sanitizedBranchName !== 'main') {
        // Construct the API URL by replacing 'keep-api' with 'keep-api-{sanitizedBranchName}'
        apiUrl = apiUrl.replace('keep-api', `keep-api-${sanitizedBranchName}`);
    }
  }
  return apiUrl;
}
