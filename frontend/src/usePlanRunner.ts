import {useRef,useState} from 'react';
import {ApiError,createApiClient,streamJob} from './api';
import {createRetrieval,type InputKind,type Lang,type Retrieval} from './productTypes';
type Draft={kind:InputKind;text:string;url:string;context:string;language:Lang;file:File|null;sourceUrl?:string;returnedUrl?:string;extractedOriginal?:string;retrievedAt?:string;extractionJobId?:string};
type Pending={id:string;requestId:string;path:string;revision:string;draft:Draft};
const BASE=(import.meta.env.VITE_API_BASE||'').replace(/\/+$/,'');
export function usePlanRunner(){
 const token=useRef(''),client=useRef<ReturnType<typeof createApiClient>|null>(null);if(!client.current)client.current=createApiClient(BASE,token);
 const pendingRef=useRef<Pending|null>(null),draftRef=useRef<Draft|null>(null);const lock=useRef(false);
 const [busy,setBusy]=useState(false),[stage,setStage]=useState(''),[error,setError]=useState(''),[pending,setPending]=useState(false),[prepared,setPrepared]=useState<Partial<Draft>>({});
 function keep(value:Pending|null){pendingRef.current=value;setPending(!!value)}
 async function one(path:string,body:object|File,draft:Draft,existing?:Pending){
  if(import.meta.env.MODE==='alpha')throw new Error('analysis_paused');
  const work=existing||{id:'',requestId:crypto.randomUUID(),path,revision:crypto.randomUUID(),draft};keep(work);
  if(!token.current)await client.current!.refresh();
  if(!work.id){
   const started=existing?await client.current!.request('/api/requests/'+work.requestId):await client.current!.request(path+(body instanceof File?'?revision='+work.revision+'&request_id='+work.requestId:''),{method:'POST',body:body instanceof File?body:JSON.stringify({...body,revision:work.revision,request_id:work.requestId})});
   work.id=started.job_id;keep(work);
  }
  let data:any;const deadline=Date.now()+600000;
  if(import.meta.env.MODE!=='test'){try{data=await streamJob(BASE+'/api/jobs/'+work.id+'/stream',token.current,setStage)}catch{/* Poll the same job; never repeat a submitted operation. */}}
  while(!['succeeded','failed'].includes(data?.status)&&Date.now()<deadline){data=await client.current!.request('/api/jobs/'+work.id);setStage(data.stage);if(['succeeded','failed'].includes(data.status))break;await new Promise(resolve=>setTimeout(resolve,1200))}
  if(data?.status==='failed'){keep(null);throw new Error(data.error||'unexpected')}
  if(data?.status!=='succeeded')throw new Error('timeout');keep(null);return path.startsWith('/api/extract/')?{...data.result,extractionJobId:work.id}:data.result;
 }
 async function run(draft?:Draft):Promise<Retrieval|null>{
  if(lock.current)return null;lock.current=true;setBusy(true);setError('');setStage('queued');
  const existing=pendingRef.current;let value=existing?.draft||draft||draftRef.current;
  try{
   if(!value)throw new Error('invalid_input');value={...value};draftRef.current=value;
   let result:any;
   if(value.kind==='research')result=await one('/api/research',{query:value.text,context:value.context,language:value.language},value,existing||undefined);
   else{
    if((value.kind==='link'||value.kind==='image')&&!value.extractedOriginal){
     const extracted=await one(value.kind==='link'?'/api/extract/link':'/api/extract/image',value.kind==='link'?{url:value.url}:value.file!,value,existing||undefined);
     value={...value,text:extracted.text,sourceUrl:extracted.requested_url||'',returnedUrl:extracted.returned_url||'',extractedOriginal:extracted.text,retrievedAt:extracted.retrieved_at||'',extractionJobId:extracted.extractionJobId};draftRef.current=value;setPrepared(value);
    }
    const useReference=['link','image'].includes(value.kind)&&!!value.extractionJobId&&value.text===value.extractedOriginal&&value.text.length>10000;
    const source=useReference?{extraction_job_id:value.extractionJobId}:{text:value.text};
    if(new TextEncoder().encode(JSON.stringify({...source,kind:value.kind,language:value.language,reviewed:false})).length>130000)throw new Error('request_too_large');
    result=await one('/api/analysis',{...source,kind:value.kind,language:value.language,reviewed:false},value,existing?.path==='/api/analysis'?existing:undefined);
   }
   return createRetrieval({input:value.text,kind:value.kind,language:value.language,result,context:value.context,sourceUrl:value.sourceUrl||'',returnedUrl:value.returnedUrl||'',extractedOriginal:value.extractedOriginal||'',retrievedAt:value.retrievedAt||''});
  }catch(e){const code=e instanceof Error?e.message:'unexpected';if(e instanceof ApiError&&e.status>=400&&e.status<500||['research_unavailable','analysis_paused','missing_key','configuration','session_expired','job_not_found','job_capacity','session_capacity','queue_full'].includes(code))keep(null);setError(code);return null}
  finally{lock.current=false;setBusy(false);setStage('')}
 }
 return {busy,stage,error,pending,prepared,run,clear(){if(lock.current||pendingRef.current)return;setError('');setPrepared({});draftRef.current=null}};
}
