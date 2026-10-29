import {createClient} from '@supabase/supabase-js';
import {emptyData,type ContentRecord,type Operation,type WorkspaceData} from './productTypes';
export interface CloudStore{pull():Promise<WorkspaceData>;apply(operation:Operation):Promise<ContentRecord>}
export function createCloudStore(url:string,key:string,getToken:()=>Promise<string|null>):CloudStore{
 const client=createClient(url,key,{accessToken:getToken});
 async function fetchRows(table:string){
  const rows:any[]=[];
  for(let offset=0;;offset+=500){
   const {data,error}=await client.from(table).select('data,revision,updated_at,deleted').order('id').range(offset,offset+499);
   if(error)throw new Error('sync_failed');rows.push(...data||[]);if(!data||data.length<500)return rows;
  }
 }
 return {
  async pull(){
   const [retrievals,tasks]=await Promise.all([fetchRows('retrievals'),fetchRows('tasks')]);
   const decode=(row:any)=>({...row.data,revision:row.revision,updatedAt:row.updated_at,deleted:row.deleted});
   return {...emptyData(),retrievals:retrievals.map(decode),tasks:tasks.map(decode)};
  },
  async apply(operation){
   let revision=operation.baseRevision;
   for(let attempt=0;attempt<4;attempt++){
    const {data,error}=await client.rpc('apply_workspace_change',{table_name:operation.table,record_id:operation.recordId,base_revision:revision,changes:operation.patch});
    if(error||!data)throw new Error('sync_failed');
    const record={...data.data,revision:data.revision,updatedAt:data.updated_at,deleted:data.deleted} as ContentRecord;
    if(data.deleted||!data.conflict)return record;
    // Reapply only the user's changed fields against the fresh server revision.
    revision=data.revision;
   }
   throw new Error('sync_conflict');
  }
 };
}
export function mergePending(remote:WorkspaceData,pending:Operation[]):WorkspaceData{
 const next=structuredClone(remote);next.outbox=pending;
 for(const operation of pending){
  const rows=next[operation.table] as ContentRecord[];const index=rows.findIndex(row=>row.id===operation.recordId);
  if(index>=0){if(!rows[index].deleted)rows[index]={...rows[index],...operation.patch} as ContentRecord}
  else rows.push(operation.patch as ContentRecord);
 }
 const deletedParents=new Set(next.retrievals.filter(row=>row.deleted).map(row=>row.id));
 next.tasks=next.tasks.map(task=>deletedParents.has(task.retrievalId)?{...task,deleted:true}:task);
 return next;
}
