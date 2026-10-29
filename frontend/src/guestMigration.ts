import {updateWorkspace} from './localStore';
import type {WorkspaceData,RecordType,ContentRecord} from './productTypes';
const fields=['title','completed','saved','dueDate','dueTime','dueTimezone'] as const;
const taskMatches=(a:any,b:any)=>fields.every(key=>a[key]===b[key]);
const later=(a:{updatedAt:string},b:{updatedAt:string})=>Date.parse(a.updatedAt)>Date.parse(b.updatedAt);
// Claims prevent the same guest history from being uploaded to another account
// during an interrupted migration. No guest content is removed before cloud ack.
export async function claimGuestPlans(owner:string){
 return updateWorkspace('guest',data=>{const claims={...data.claims};for(const row of data.retrievals)if(!row.deleted&&!claims[row.id])claims[row.id]=owner;return {...data,claims}});
}
export function migrationRecords(guest:WorkspaceData,owner:string,account:WorkspaceData){
 const parents=guest.retrievals.filter(row=>!row.deleted&&guest.claims?.[row.id]===owner);
 const missingParents=parents.filter(row=>!account.retrievals.some(existing=>existing.id===row.id));
 const tasks=guest.tasks.filter(task=>!task.deleted&&parents.some(row=>row.id===task.retrievalId)&&!account.retrievals.some(row=>row.id===task.retrievalId&&row.deleted)&&!account.tasks.some(row=>row.id===task.id));
 const updates:{table:RecordType;id:string;patch:Partial<ContentRecord>}[]=[];
 for(const row of parents){const saved=account.retrievals.find(saved=>saved.id===row.id);if(saved&&!saved.deleted&&later(row,saved)&&row.title!==saved.title)updates.push({table:'retrievals',id:row.id,patch:{title:row.title}})}
 for(const task of guest.tasks.filter(task=>!task.deleted&&parents.some(row=>row.id===task.retrievalId))){const saved=account.tasks.find(saved=>saved.id===task.id);if(saved&&!saved.deleted&&later(task,saved)&&!taskMatches(task,saved))updates.push({table:'tasks',id:task.id,patch:{title:task.title,completed:task.completed,saved:task.saved,dueDate:task.dueDate,dueTime:task.dueTime,dueTimezone:task.dueTimezone}})}
 return updates.length?{retrievals:missingParents,tasks,updates}:{retrievals:missingParents,tasks};
}
export async function finishGuestMigration(owner:string,account:WorkspaceData){
 if(account.outbox.length)return;
 await updateWorkspace('guest',data=>{
  const completed=new Set(data.retrievals.filter(row=>data.claims?.[row.id]===owner).filter(row=>{
   const saved=account.retrievals.find(saved=>saved.id===row.id&&saved.revision>0);if(!saved)return false;
   if(!saved.deleted&&later(row,saved)&&row.title!==saved.title)return false;
   return saved.deleted||data.tasks.filter(task=>task.retrievalId===row.id&&!task.deleted).every(task=>account.tasks.some(saved=>saved.id===task.id&&saved.revision>0&&(saved.deleted||!later(task,saved)||taskMatches(task,saved))));
  }).map(row=>row.id));
  // Keep ownership-only markers so a stale guest tab cannot re-import the same
  // IDs into a different account. These markers contain no plan text.
  return {...data,retrievals:data.retrievals.filter(row=>!completed.has(row.id)),tasks:data.tasks.filter(task=>!completed.has(task.retrievalId))};
 });
}
