import {APIError} from './apiResponse.ts';

export function expiredRuntimeReference(error:unknown,knownReference=true){
  return knownReference&&error instanceof APIError&&[403,404].includes(error.status);
}

export function missingSavedConfiguration(error:unknown,config:unknown){
  return error instanceof APIError&&error.status===404&&config!==undefined;
}

export function forgetRuntimeReferences(storage:Pick<Storage,'removeItem'>,key:string){
  // Keep physical settings and the workspace capability. Drop only expired run IDs.
  for(const suffix of ['session','token','world'])storage.removeItem(`vivacity:${key}:${suffix}`);
}
