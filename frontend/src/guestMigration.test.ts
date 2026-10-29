import 'fake-indexeddb/auto';
import {webcrypto} from 'node:crypto';
import {beforeEach,expect,it,vi} from 'vitest';
import {claimGuestPlans,migrationRecords,finishGuestMigration} from './guestMigration';
import {loadWorkspace,saveWorkspace,clearWorkspace} from './localStore';
import {createRetrieval,candidateTasks,emptyData,type PlanResult} from './productTypes';
import examples from '../public/examples.json';
const make=()=>createRetrieval({input:'Synthetic migration fixture',kind:'ask',language:'en',result:structuredClone(examples['en-general'].result) as PlanResult});
beforeEach(async()=>{vi.stubGlobal('crypto',webcrypto);await clearWorkspace('guest')});
it('claims history for one account without removing its unsynced contents',async()=>{
 const row=make();await saveWorkspace('guest',{...emptyData(),retrievals:[row],tasks:candidateTasks(row)});
 const claimed=await claimGuestPlans('owner-one');expect(claimed.retrievals[0].id).toBe(row.id);
 expect(migrationRecords(await claimGuestPlans('owner-two'),'owner-two',emptyData()).retrievals).toEqual([]);
 expect(migrationRecords(claimed,'owner-one',emptyData()).retrievals[0].id).toBe(row.id);
 await finishGuestMigration('owner-one',emptyData());expect((await loadWorkspace('guest')).retrievals).toHaveLength(1);
});
it('preserves guest history until every parent and task has cloud acknowledgement',async()=>{
 const row=make(),tasks=candidateTasks(row);await saveWorkspace('guest',{...emptyData(),retrievals:[row],tasks});await claimGuestPlans('one');
 const account={...emptyData(),retrievals:[{...row,revision:1}],tasks:tasks.slice(1).map(task=>({...task,revision:1}))};
 await finishGuestMigration('one',account);expect((await loadWorkspace('guest')).retrievals).toHaveLength(1);
 const missing=migrationRecords(await loadWorkspace('guest'),'one',account);expect(missing.retrievals).toEqual([]);expect(missing.tasks.map(task=>task.id)).toEqual([tasks[0].id]);
});
it('moves only acknowledged history, retaining newly added guest records',async()=>{
 const row=make(),other=make(),tasks=candidateTasks(row);await saveWorkspace('guest',{...emptyData(),retrievals:[row],tasks});await claimGuestPlans('one');
 const guest=await loadWorkspace('guest');await saveWorkspace('guest',{...guest,retrievals:[...guest.retrievals,other]});
 const account={...emptyData(),retrievals:[{...row,revision:1}],tasks:tasks.map(task=>({...task,revision:1}))};
 await finishGuestMigration('one',account);expect((await loadWorkspace('guest')).retrievals.map(row=>row.id)).toEqual([other.id]);
});
it('does not resurrect a cloud-deleted retrieval during resumed migration',async()=>{
 const row=make();await saveWorkspace('guest',{...emptyData(),retrievals:[row],tasks:candidateTasks(row)});const guest=await claimGuestPlans('one');
 const account={...emptyData(),retrievals:[{...row,revision:2,deleted:true}]};expect(migrationRecords(guest,'one',account)).toEqual({retrievals:[],tasks:[]});
 await finishGuestMigration('one',account);expect((await loadWorkspace('guest')).retrievals).toEqual([]);
});
it('retains ownership after a stale guest tab writes its older snapshot',async()=>{
 const row=make(),stale={...emptyData(),retrievals:[row]};await saveWorkspace('guest',stale);await claimGuestPlans('one');
 await finishGuestMigration('one',{...emptyData(),retrievals:[{...row,revision:1}]});
 await saveWorkspace('guest',stale);
 const guest=await claimGuestPlans('two');expect(guest.claims?.[row.id]).toBe('one');
 expect(migrationRecords(guest,'two',emptyData()).retrievals).toEqual([]);
});
it('queues newer guest edits and retains them until acknowledged',async()=>{
 const row=make(),task=candidateTasks(row)[0],old='2026-10-24T00:00:00Z',newer='2026-10-24T01:00:00Z';
 const guestRow={...row,title:'New personal title',updatedAt:newer},guestTask={...task,completed:true,updatedAt:newer};
 await saveWorkspace('guest',{...emptyData(),retrievals:[guestRow],tasks:[guestTask]});const guest=await claimGuestPlans('one');
 const account={...emptyData(),retrievals:[{...row,revision:1,updatedAt:old}],tasks:[{...task,revision:1,updatedAt:old}]};
 expect(migrationRecords(guest,'one',account).updates?.map(update=>update.table)).toEqual(['retrievals','tasks']);
 await finishGuestMigration('one',account);expect((await loadWorkspace('guest')).retrievals).toHaveLength(1);
 await finishGuestMigration('one',{...account,retrievals:[{...guestRow,revision:2}],tasks:[{...guestTask,revision:2}]});
 expect((await loadWorkspace('guest')).retrievals).toEqual([]);
});
