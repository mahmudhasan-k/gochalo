import type {ContentRecord,WorkspaceData,RecordType} from './productTypes';
const same=(a:unknown,b:unknown)=>JSON.stringify(a)===JSON.stringify(b);
// Apply only this tab's changes inside an IndexedDB transaction. A full stale
// snapshot must not erase another tab's queued edits or revive an acknowledged op.
export function mergeCacheDelta(latest:WorkspaceData,before:WorkspaceData,after:WorkspaceData):WorkspaceData{
 const next=structuredClone(latest);
 for(const table of ['retrievals','tasks'] as RecordType[]){
  const rows=new Map<string,ContentRecord>((next[table] as ContentRecord[]).map(row=>[row.id,row]));
  const previous=new Map<string,ContentRecord>((before[table] as ContentRecord[]).map(row=>[row.id,row]));
  for(const row of after[table] as ContentRecord[]){
   const old=previous.get(row.id),stored=rows.get(row.id);
   if(old&&same(old,row))continue;
   if(stored?.deleted&&!row.deleted)continue;
   if(!stored){rows.set(row.id,structuredClone(row));continue}
   if(stored.revision>row.revision)continue;
   if(!old){if(row.revision>stored.revision)rows.set(row.id,structuredClone(row));continue}
   const patch=Object.fromEntries(Object.entries(row).filter(([key,value])=>!same(value,(old as any)[key])));
   rows.set(row.id,{...stored,...patch} as ContentRecord);
  }
  const present=new Set(after[table].map(row=>row.id));
  for(const old of before[table])if(!present.has(old.id)&&rows.get(old.id)?.revision===old.revision)rows.delete(old.id);
  (next[table] as ContentRecord[])=Array.from(rows.values());
 }
 const previousOps=new Set(before.outbox.map(op=>op.id)),remaining=new Set(after.outbox.map(op=>op.id));
 const removed=new Set(before.outbox.filter(op=>!remaining.has(op.id)).map(op=>op.id));
 next.outbox=next.outbox.filter(op=>!removed.has(op.id));
 const known=new Set(next.outbox.map(op=>op.id));
 for(const op of after.outbox)if(!previousOps.has(op.id)&&!known.has(op.id)){next.outbox.push(structuredClone(op));known.add(op.id)}
 for(const op of next.outbox){const rows=next[op.table] as ContentRecord[];const index=rows.findIndex(row=>row.id===op.recordId);if(index>=0&&!rows[index].deleted)rows[index]={...rows[index],...op.patch} as ContentRecord}
 const deleted=new Set(next.retrievals.filter(row=>row.deleted).map(row=>row.id));
 next.tasks=next.tasks.map(row=>deleted.has(row.retrievalId)?{...row,deleted:true}:row);
 const claims={...latest.claims,...after.claims};if(Object.keys(claims).length)next.claims=claims;
 return next;
}
