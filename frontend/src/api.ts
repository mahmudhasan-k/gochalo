// Bound both receiving headers and reading the response body. A timed-out POST
// may still run on the server; callers must not automatically submit it again.
export const REQUEST_TIMEOUT_MS=30000;
export class ApiError extends Error{
 constructor(public code:string,public status=0){super(code)}
}
export async function requestJson(url:string,token:string,options:RequestInit={}){
 const controller=new AbortController();
 const timer=setTimeout(()=>controller.abort(),REQUEST_TIMEOUT_MS);
 try{
  const response=await fetch(url,{...options,signal:controller.signal,headers:{
   ...(options.body instanceof File?{'Content-Type':options.body.type}:options.body instanceof FormData?{}:{'Content-Type':'application/json'}),
   'X-Session-Token':token,...options.headers
  }});
  if(!response.ok){
   const payload=await response.json().catch(()=>({detail:'network_error'}));
   throw new ApiError(payload&&typeof payload.detail==='string'?payload.detail:'invalid_input',response.status);
  }
  return await response.json();
 }catch(error){
  if(controller.signal.aborted)throw new Error('timeout');
  throw error;
 }finally{clearTimeout(timer)}
}

export function createApiClient(base:string,session:{current:string}){
 let refreshing:Promise<void>|null=null;
 async function refresh(){
  if(!refreshing)refreshing=requestJson(base+'/api/session','',{method:'POST'}).then(data=>{
   if(typeof data.token!=='string'||!data.token)throw new Error('session_expired');
   session.current=data.token;
  }).finally(()=>{refreshing=null});
  return refreshing;
 }
 async function request(path:string,options:RequestInit={}){
  const protectedRoute=!['/api/session','/api/health','/api/example'].includes(path.split('?')[0]);
  const attemptedToken=session.current;
  try{return await requestJson(base+path,attemptedToken,options)}catch(error){
   if(!protectedRoute||!(error instanceof ApiError)||![401,403].includes(error.status))throw error;
   // A stale parallel response must not replace a token another request refreshed.
   if(session.current===attemptedToken)await refresh();
   return requestJson(base+path,session.current,options);
  }
 }
 return {request,refresh};
}

export async function streamJob(url:string,token:string,onStage:(stage:string)=>void):Promise<any>{
 const controller=new AbortController();
 let timer=setTimeout(()=>controller.abort(),20000);
 const touch=()=>{clearTimeout(timer);timer=setTimeout(()=>controller.abort(),20000)};
 let reader:ReadableStreamDefaultReader<Uint8Array>|undefined;
 try{
  const response=await fetch(url,{headers:{Accept:'text/event-stream','X-Session-Token':token},signal:controller.signal});
  if(!response.ok||!response.headers.get('content-type')?.includes('text/event-stream')||!response.body)throw new Error('stream_unavailable');
  touch();reader=response.body.getReader();
  const decoder=new TextDecoder();let buffer='';
  while(true){
   const {done,value}=await reader.read();
   if(done)throw new Error('stream_disconnected');
   touch();buffer=(buffer+decoder.decode(value,{stream:true})).replace(/\r\n/g,'\n');
   // This is a stage stream, not generated tokens. Bound malformed event buffers.
   if(buffer.length>2000000)throw new Error('stream_invalid');
   let boundary;
   while((boundary=buffer.indexOf('\n\n'))!==-1){
    const block=buffer.slice(0,boundary);buffer=buffer.slice(boundary+2);
    const data=block.split('\n').filter(line=>line.startsWith('data:')).map(line=>line.slice(5).trimStart()).join('\n');
    if(!data)continue;
    const event=JSON.parse(data);if(typeof event.stage==='string')onStage(event.stage);
    if(event.status==='succeeded'||event.status==='failed')return event;
   }
  }
 }finally{clearTimeout(timer);controller.abort();await reader?.cancel().catch(()=>{})}
}
