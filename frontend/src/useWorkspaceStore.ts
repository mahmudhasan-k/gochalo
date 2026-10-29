import {useCallback,useEffect,useRef,useState} from 'react';
import {clearWorkspace,loadWorkspace,saveWorkspaceDelta} from './localStore';
import {mergePending,type CloudStore} from './cloudStore';
import {emptyData,type ContentRecord,type RecordType,type WorkspaceData} from './productTypes';
export function useWorkspaceStore(namespace:string,cloud:CloudStore|null){
 const [state,setState]=useState<WorkspaceData>(emptyData),[ready,setReady]=useState(''),[status,setStatus]=useState('loading'),[storageError,setStorageError]=useState(false);
 const current=useRef({namespace,data:emptyData(),generation:0});const saving=useRef(Promise.resolve());const syncing=useRef<number|null>(null);const dirty=useRef(false);const writable=useRef(true);const suspended=useRef(false);
 const publish=useCallback((data:WorkspaceData,store=true)=>{
  const before=current.current.data;current.current.data=data;setState(data);
  if(store){const ns=current.current.namespace,gen=current.current.generation;saving.current=saving.current.catch(()=>{}).then(async()=>{
   if(gen!==current.current.generation)return;
   if(!writable.current)throw new Error('storage_invalid');
   const merged=await saveWorkspaceDelta(ns,before,data);
   if(gen===current.current.generation&&current.current.data===data){current.current.data=merged;setState(merged);if(cloud&&merged.outbox.length)setStatus('pending')}
  }).then(()=>{if(gen===current.current.generation){setStorageError(false);if(!cloud)setStatus('device')}}).catch(()=>{if(gen===current.current.generation){setStorageError(true);if(!cloud)setStatus('unsaved')}})}
 },[cloud]);
 useEffect(()=>{
  const generation=++current.current.generation;current.current.namespace=namespace;current.current.data=emptyData();dirty.current=false;writable.current=true;suspended.current=false;setState(emptyData());setReady('');setStatus('loading');setStorageError(false);
  void loadWorkspace(namespace).then(data=>{if(current.current.generation!==generation)return;publish(data,false);setStatus(cloud?(data.outbox.length?'pending':'synced'):'device')}).catch(error=>{if(current.current.generation!==generation)return;if(error.message==='storage_invalid')writable.current=false;setStorageError(true);setStatus('unsaved')}).finally(()=>{if(current.current.generation===generation)setReady(namespace)});
  return()=>{current.current.generation++};
 },[namespace,cloud,publish]);
 const change=useCallback((table:RecordType,id:string,patch:Partial<ContentRecord>)=>{
  if(suspended.current||ready!==namespace||current.current.namespace!==namespace)throw new Error('workspace_loading');
  const data=current.current.data;const rows=data[table] as ContentRecord[];const existing=rows.find(row=>row.id===id);if(existing?.deleted)return;
  const changes={...patch,updatedAt:new Date().toISOString()};const record={...existing,...changes} as ContentRecord;
  const next={...data,[table]:existing?rows.map(row=>row.id===id?record:row):[...rows,record]};
  if(cloud)next.outbox=[...data.outbox,{id:crypto.randomUUID(),table,recordId:id,patch:changes,baseRevision:existing?.revision||0,createdAt:new Date().toISOString()}];
  dirty.current=true;publish(next);if(cloud)setStatus('pending');
 },[cloud,publish,ready,namespace]);
 const sync=useCallback(async()=>{
  if(suspended.current||!cloud||syncing.current===current.current.generation||ready!==namespace)return;
  const generation=current.current.generation;syncing.current=generation;setStatus('syncing');
  try{
   // FIFO preserves parent creation before task creation and makes imports resumable.
   while(current.current.data.outbox.length&&current.current.generation===generation){
    const operation=current.current.data.outbox[0];const record=await cloud.apply(operation);
    if(current.current.generation!==generation)return;
    const data=current.current.data;const remaining=data.outbox.filter(item=>item.id!==operation.id);
    const rows=(data[operation.table] as ContentRecord[]).filter(row=>row.id!==record.id);
    const base={...data,[operation.table]:[...rows,record],outbox:[]} as WorkspaceData;
    publish(mergePending(base,remaining));
   }
   const remote=await cloud.pull();if(current.current.generation!==generation)return;
   publish(mergePending(remote,current.current.data.outbox));await saving.current;
   if(current.current.generation===generation)setStatus(current.current.data.outbox.length?'pending':'synced');
  }catch{if(current.current.generation===generation)setStatus('sync_failed')}
  finally{if(syncing.current===generation)syncing.current=null}
 },[cloud,namespace,ready,publish]);
 useEffect(()=>{if(ready===namespace&&cloud)void sync()},[ready,namespace,cloud,sync]);
 useEffect(()=>{const refresh=()=>{if(document.visibilityState!=='hidden')void sync()};window.addEventListener('online',refresh);window.addEventListener('focus',refresh);document.addEventListener('visibilitychange',refresh);return()=>{window.removeEventListener('online',refresh);window.removeEventListener('focus',refresh);document.removeEventListener('visibilitychange',refresh)}},[sync]);
 useEffect(()=>{if(status!=='pending')return;const timer=setTimeout(()=>void sync(),350);return()=>clearTimeout(timer)},[status,state.outbox.length,sync]);
 useEffect(()=>{const before=(event:BeforeUnloadEvent)=>{if(current.current.data.outbox.length||dirty.current&&status==='unsaved'){event.preventDefault();event.returnValue=''}};window.addEventListener('beforeunload',before);return()=>window.removeEventListener('beforeunload',before)},[status]);
 return {data:ready===namespace?state:emptyData(),ready:ready===namespace,status,storageError,change,sync,
  async clear(){suspended.current=true;const generation=++current.current.generation;await saving.current;await clearWorkspace(namespace);if(current.current.generation===generation&&current.current.namespace===namespace)publish(emptyData(),false)},
  pending:state.outbox.length, snapshot:()=>current.current.data};
}
