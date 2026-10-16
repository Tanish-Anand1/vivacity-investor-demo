export function runtimeEndpoints(production:boolean,configuredBackend:string|undefined,origin:string){
  const backend=(configuredBackend??(production&&origin.startsWith('https:')?'https://vivacity-runtime.onrender.com':'http://127.0.0.1:8000')).replace(/\/$/,'');
  return {http:production?`${origin}/runtime`:backend,backend};
}

export function runtimeSocketURL(backend:string,id:string,kind:'events'|'live',after?:number){
  // Vercel HTTP rewrites do not carry WebSockets. Keep the native Render stream.
  const url=new URL(`/v1/experiments/${encodeURIComponent(id)}/${kind}`,backend);
  url.protocol=url.protocol==='https:'?'wss:':'ws:';
  if(after!==undefined)url.searchParams.set('after',String(after));
  return url.href;
}

export const CONNECTION_ERROR='The simulation connection was interrupted. Reconnect to try again.';
export const TIMEOUT_ERROR='The simulation service is taking too long to respond. It may be starting up; reconnect to try again.';
export function isConnectionMessage(message:string|null){
  return message==='Failed to fetch'||message===CONNECTION_ERROR||message===TIMEOUT_ERROR||
    /^50[234]: The simulation service/.test(message??'');
}

type TransportOptions={fetcher?:typeof fetch;wait?:(ms:number)=>Promise<void>;timeoutMs?:number};
export async function fetchRuntime(url:string,init:RequestInit={},options:TransportOptions={}):Promise<Response>{
  const readOnly=['GET','HEAD'].includes((init.method??'GET').toUpperCase());
  const attempts=readOnly?3:1;
  const fetcher=options.fetcher??fetch;
  const wait=options.wait??((ms:number)=>new Promise<void>(resolve=>setTimeout(resolve,ms)));
  for(let attempt=0;attempt<attempts;attempt++){
    const timeout=AbortSignal.timeout(options.timeoutMs??(readOnly?20000:60000));
    const signal=init.signal?AbortSignal.any([init.signal,timeout]):timeout;
    try{
      const response=await fetcher(url,{...init,cache:'no-store',signal});
      if(readOnly&&[502,503,504].includes(response.status)&&attempt<attempts-1){
        await response.body?.cancel();
      }else return response;
    }catch(error){
      if(init.signal?.aborted)throw error;
      const networkFailure=error instanceof TypeError||timeout.aborted;
      if(!networkFailure)throw error;
      if(attempt===attempts-1)throw new Error(timeout.aborted?TIMEOUT_ERROR:CONNECTION_ERROR);
    }
    // Only reads are retried: a lost POST/PATCH response may already have applied.
    await wait(1000*(attempt+1));
  }
  throw new Error(CONNECTION_ERROR);
}
