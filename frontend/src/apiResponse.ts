export class APIError extends Error{
  status:number;detail:unknown;
  constructor(status:number,detail:unknown){super(typeof detail==='string'?detail:JSON.stringify(detail));this.status=status;this.detail=detail;}
}
export async function readAPIResponse(response:Response):Promise<unknown>{
  let data;
  try{data=await response.json();}
  catch{throw new APIError(response.status||503,response.ok?'The simulation service returned an unreadable response.':'The simulation service is temporarily unavailable. Try again.');}
  if(!response.ok)throw new APIError(response.status,data?.detail??data);
  return data;
}
