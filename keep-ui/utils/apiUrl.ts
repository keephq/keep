

export function getApiURL(): string {
    // https://github.com/vercel/next.js/issues/5354#issuecomment-520305040
    // https://stackoverflow.com/questions/49411796/how-do-i-detect-whether-i-am-on-server-on-client-in-next-js

    // Some background on this:
    // On docker-compose, the browser can't access the "http://keep-backend" url
    // since its the name of the container (and not accesible from the host)
    // so we need to use the "http://localhost:3000" url instead.
    const componentType = typeof window === 'undefined' ? 'server' : 'client';

    if (componentType === 'server') {
        return process.env.API_URL!;
    }else{
        return process.env.NEXT_PUBLIC_API_URL!;
    }
  }
