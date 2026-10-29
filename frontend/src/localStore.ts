import {mergeCacheDelta} from './cacheMerge';
import {emptyData,type WorkspaceData} from './productTypes';
const DATABASE='gochalo-workspace-v1';
let opening:Promise<IDBDatabase>|undefined;
function open(){
 if(!opening)opening=new Promise<IDBDatabase>((resolve,reject)=>{
  if(!globalThis.indexedDB){reject(new Error('storage_unavailable'));return}
  const request=indexedDB.open(DATABASE,1);
  request.onupgradeneeded=()=>request.result.createObjectStore('workspaces');
  request.onerror=()=>reject(new Error('storage_unavailable'));
  request.onblocked=()=>reject(new Error('storage_blocked'));
  request.onsuccess=()=>{request.result.onversionchange=()=>{request.result.close();opening=undefined};resolve(request.result)};
 }).catch(error=>{opening=undefined;throw error});
 return opening;
}
export async function loadWorkspace(namespace:string):Promise<WorkspaceData>{
 const db=await open();return new Promise((resolve,reject)=>{
  const transaction=db.transaction('workspaces','readonly');const request=transaction.objectStore('workspaces').get(namespace);
  request.onsuccess=()=>{const value=request.result;if(!value){resolve(emptyData());return}if(value.version!==1||!Array.isArray(value.data?.retrievals)||!Array.isArray(value.data?.tasks)||!Array.isArray(value.data?.outbox)){reject(new Error('storage_invalid'));return}resolve(value.data)};
  request.onerror=()=>reject(new Error('storage_unavailable'));
 });
}
export async function saveWorkspace(namespace:string,data:WorkspaceData){
 const db=await open();return new Promise<void>((resolve,reject)=>{
  const transaction=db.transaction('workspaces','readwrite'),store=transaction.objectStore('workspaces');
  if(namespace==='guest'){const existing=store.get(namespace);existing.onsuccess=()=>{const claims={...existing.result?.data?.claims,...data.claims};store.put({version:1,data:Object.keys(claims).length?{...data,claims}:data},namespace)}}
  else store.put({version:1,data},namespace);
  transaction.oncomplete=()=>resolve();transaction.onerror=()=>reject(new Error('storage_unavailable'));transaction.onabort=()=>reject(new Error('storage_unavailable'));
 });
}
export async function updateWorkspace(namespace:string,update:(data:WorkspaceData)=>WorkspaceData){
 const db=await open();return new Promise<WorkspaceData>((resolve,reject)=>{
  const tx=db.transaction('workspaces','readwrite'),store=tx.objectStore('workspaces'),get=store.get(namespace);let next:WorkspaceData;
  get.onsuccess=()=>{try{const value=get.result;if(value&&(value.version!==1||!Array.isArray(value.data?.retrievals)||!Array.isArray(value.data?.tasks)||!Array.isArray(value.data?.outbox)))throw new Error('storage_invalid');next=update(value?.data||emptyData());store.put({version:1,data:next},namespace)}catch{tx.abort()}};
  tx.oncomplete=()=>resolve(next);tx.onerror=()=>reject(new Error('storage_unavailable'));tx.onabort=()=>reject(new Error('storage_unavailable'));
 });
}
export async function clearWorkspace(namespace:string){
 const db=await open();return new Promise<void>((resolve,reject)=>{const tx=db.transaction('workspaces','readwrite');tx.objectStore('workspaces').delete(namespace);tx.oncomplete=()=>resolve();tx.onerror=()=>reject(new Error('storage_unavailable'))});
}
export function closeLocalStore(){opening?.then(db=>db.close());opening=undefined}
export function readPreference(key:string,fallback:boolean){try{const value=localStorage.getItem('gochalo:'+key);return value===null?fallback:value==='true'}catch{return fallback}}
export function writePreference(key:string,value:boolean){try{localStorage.setItem('gochalo:'+key,String(value))}catch{/* In-memory preference remains usable. */}}
export async function legacyCompletion(retrieval:{result:unknown;input:string;language:string}):Promise<Set<string>>{
 try{const original={...(retrieval.result as Record<string,unknown>)};delete original.source_reviewed;
  for(const result of [retrieval.result,original]){const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify({result,source:retrieval.input,language:retrieval.language})));
  const key='shobuj-checklist-v1:'+Array.from(new Uint8Array(bytes),v=>v.toString(16).padStart(2,'0')).join('');
  const value=JSON.parse(localStorage.getItem(key)||'{}');if(Array.isArray(value.checked))return new Set(value.checked.filter((id:unknown)=>typeof id==='string'));
  }return new Set();
 }catch{return new Set()}
}

export async function saveWorkspaceDelta(namespace:string,before:WorkspaceData,after:WorkspaceData){
 return updateWorkspace(namespace,latest=>mergeCacheDelta(latest,before,after));
}
