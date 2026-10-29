import {useEffect,useState} from 'react';
const PREFIX='shobuj-checklist-v1:';
type ChecklistResult={sections:Record<string,{text:string}[]>;evidence:unknown[]};
export function useChecklist(result:ChecklistResult|null,source:string,language:string){
 const [checked,setChecked]=useState<Record<string,boolean>>({});
 const [key,setKey]=useState('');const [ready,setReady]=useState(false);
 useEffect(()=>{
  let cancelled=false;setReady(false);setChecked({});setKey('');
  if(!result)return;
  const allowed=new Set(['steps','documents'].flatMap(section=>(result.sections[section]||[]).map((_,i)=>section+':'+i)));
  void (async()=>{
   try{
    const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify({result,source,language})));
    const storageKey=PREFIX+Array.from(new Uint8Array(digest),v=>v.toString(16).padStart(2,'0')).join('');
    let saved:string[]=[];
    try{const value=JSON.parse(localStorage.getItem(storageKey)||'{}');if(Array.isArray(value.checked))saved=value.checked.filter((v:unknown)=>typeof v==='string'&&allowed.has(v))}catch{/* Storage is optional; retain in-page progress. */}
    if(!cancelled){setKey(storageKey);setChecked(Object.fromEntries(saved.map(id=>[id,true])))}
   }catch{/* Non-secure or restricted browsers still get an in-memory checklist. */}
   finally{if(!cancelled)setReady(true)}
  })();
  return()=>{cancelled=true};
 },[result,source,language]);
 function save(next:Record<string,boolean>){
  setChecked(next);if(!key)return;
  try{
   // Persist completion flags only: no notice text, excerpts, tokens or filenames.
   localStorage.setItem(key,JSON.stringify({checked:Object.keys(next).filter(id=>next[id]),updated:Date.now()}));
   const entries=Object.keys(localStorage).filter(k=>k.startsWith(PREFIX));
   const ordered=entries.map(k=>{try{return {k,updated:JSON.parse(localStorage.getItem(k)||'{}').updated||0}}catch{return {k,updated:0}}}).sort((a,b)=>b.updated-a.updated);
   for(const old of ordered.slice(20))if(old.k!==key)localStorage.removeItem(old.k);
  }catch{/* Quota/permission failures must never remove the result or draft. */}
 }
 return {checked,ready,toggle:(id:string)=>save({...checked,[id]:!checked[id]}),reset:()=>save({})};
}
