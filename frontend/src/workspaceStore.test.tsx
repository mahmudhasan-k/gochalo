import 'fake-indexeddb/auto';
import {webcrypto} from 'node:crypto';
import {act,cleanup,renderHook,waitFor} from '@testing-library/react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {useWorkspaceStore} from './useWorkspaceStore';
import {loadWorkspace,saveWorkspace} from './localStore';
import {createRetrieval,candidateTasks,emptyData,type ContentRecord,type WorkspaceData,type PlanResult,type Operation} from './productTypes';
import type {CloudStore} from './cloudStore';
import examples from '../public/examples.json';
beforeEach(()=>vi.stubGlobal('crypto',webcrypto));
afterEach(()=>{cleanup();vi.unstubAllGlobals()});
const row=()=>createRetrieval({input:'Goal',kind:'ask',language:'en',result:structuredClone(examples['en-general'].result) as PlanResult});
function memoryCloud(){
 const remote=emptyData();const cloud:CloudStore={pull:vi.fn(async()=>structuredClone(remote)),apply:vi.fn(async (operation:Operation)=>{
  const rows=remote[operation.table] as ContentRecord[];const existing=rows.find(record=>record.id===operation.recordId);
  const record={...existing,...operation.patch,revision:(existing?.revision||0)+1} as ContentRecord;
  const index=rows.findIndex(record=>record.id===operation.recordId);if(index>=0)rows[index]=record;else rows.push(record);return record;
 })};return {cloud,remote};
}
it('persists local changes and restores them when the workspace remounts',async()=>{
 const namespace='guest:'+crypto.randomUUID();const item=row();const hook=renderHook(()=>useWorkspaceStore(namespace,null));
 await waitFor(()=>expect(hook.result.current.ready).toBe(true));
 act(()=>hook.result.current.change('retrievals',item.id,item));
 await waitFor(async()=>expect((await loadWorkspace(namespace)).retrievals[0]?.id).toBe(item.id));hook.unmount();
 const restored=renderHook(()=>useWorkspaceStore(namespace,null));await waitFor(()=>expect(restored.result.current.data.retrievals[0]?.id).toBe(item.id));
});
it('keeps a failed sync in the durable outbox and resumes it on a later attempt',async()=>{
 const namespace='account:'+crypto.randomUUID(),item=row();const {cloud,remote}=memoryCloud();
 const hook=renderHook(()=>useWorkspaceStore(namespace,cloud));await waitFor(()=>expect(hook.result.current.status).toBe('synced'));
 vi.mocked(cloud.apply).mockRejectedValueOnce(new Error('offline'));
 act(()=>hook.result.current.change('retrievals',item.id,item));await act(async()=>hook.result.current.sync());
 expect(hook.result.current.status).toBe('sync_failed');expect(hook.result.current.pending).toBe(1);
 await waitFor(async()=>expect((await loadWorkspace(namespace)).outbox).toHaveLength(1));
 await act(async()=>hook.result.current.sync());expect(hook.result.current.pending).toBe(0);expect(remote.retrievals[0].id).toBe(item.id);
});
it('ignores old-account network results after an account switch',async()=>{
 let deliver:(data:WorkspaceData)=>void=()=>{};const old:CloudStore={pull:()=>new Promise(resolve=>{deliver=resolve}),apply:vi.fn()};
 const {cloud:next}=memoryCloud();const one='account:'+crypto.randomUUID(),two='account:'+crypto.randomUUID();
 const hook=renderHook(({namespace,cloud})=>useWorkspaceStore(namespace,cloud),{initialProps:{namespace:one,cloud:old}});
 await waitFor(()=>expect(hook.result.current.status).toBe('syncing'));
 hook.rerender({namespace:two,cloud:next});await waitFor(()=>expect(hook.result.current.status).toBe('synced'));
 await act(async()=>deliver({...emptyData(),retrievals:[row()]}));
 expect(hook.result.current.data.retrievals).toEqual([]);expect(hook.result.current.status).toBe('synced');
});
it('clear removes only the account cache and retains guest data',async()=>{
 const guest='guest:'+crypto.randomUUID(),account='account:'+crypto.randomUUID(),item=row();
 await saveWorkspace(guest,{...emptyData(),retrievals:[item]});await saveWorkspace(account,{...emptyData(),retrievals:[item]});
 const hook=renderHook(()=>useWorkspaceStore(account,null));await waitFor(()=>expect(hook.result.current.ready).toBe(true));
 await act(async()=>hook.result.current.clear());expect(await loadWorkspace(account)).toEqual(emptyData());expect((await loadWorkspace(guest)).retrievals[0].id).toBe(item.id);
});
it('an in-flight refresh cannot recreate the account cache after sign-out clearing',async()=>{
 const namespace='account:'+crypto.randomUUID();let deliver:(data:WorkspaceData)=>void=()=>{};
 const cloud:CloudStore={pull:()=>new Promise(resolve=>{deliver=resolve}),apply:vi.fn()};
 const hook=renderHook(()=>useWorkspaceStore(namespace,cloud));await waitFor(()=>expect(hook.result.current.status).toBe('syncing'));
 await act(async()=>hook.result.current.clear());await act(async()=>deliver({...emptyData(),retrievals:[row()]}));
 expect(hook.result.current.data.retrievals).toEqual([]);expect(await loadWorkspace(namespace)).toEqual(emptyData());
});

it('refreshes on reconnect and focus while retaining failed offline edits',async()=>{
 const namespace='account:'+crypto.randomUUID(),item=row(),{cloud,remote}=memoryCloud();
 const hook=renderHook(()=>useWorkspaceStore(namespace,cloud));await waitFor(()=>expect(hook.result.current.status).toBe('synced'));
 vi.mocked(cloud.apply).mockRejectedValueOnce(new Error('offline'));act(()=>hook.result.current.change('retrievals',item.id,item));
 await act(async()=>hook.result.current.sync());expect(hook.result.current.status).toBe('sync_failed');
 act(()=>window.dispatchEvent(new Event('online')));await waitFor(()=>expect(hook.result.current.status).toBe('synced'));
 remote.retrievals[0].title='Another device title';remote.retrievals[0].revision++;
 act(()=>window.dispatchEvent(new Event('focus')));await waitFor(()=>expect(hook.result.current.data.retrievals[0].title).toBe('Another device title'));
});

it('retains concurrent offline edits from two tabs in one durable account queue',async()=>{
 const namespace='account:'+crypto.randomUUID(),item={...row(),revision:1},task={...candidateTasks(item)[0],saved:true,revision:1};
 const {cloud,remote}=memoryCloud();remote.retrievals=[item];remote.tasks=[task];
 const apply=cloud.apply;let offline=true;cloud.apply=vi.fn(op=>offline?Promise.reject(new Error('offline')):apply(op));
 const one=renderHook(()=>useWorkspaceStore(namespace,cloud)),two=renderHook(()=>useWorkspaceStore(namespace,cloud));
 await waitFor(()=>expect(one.result.current.status).toBe('synced'));await waitFor(()=>expect(two.result.current.status).toBe('synced'));
 act(()=>one.result.current.change('tasks',task.id,{title:'Personal wording from tab one'}));
 act(()=>two.result.current.change('tasks',task.id,{completed:true}));
 await waitFor(async()=>{const cached=await loadWorkspace(namespace);expect(cached.outbox).toHaveLength(2);expect(cached.tasks[0]).toMatchObject({title:'Personal wording from tab one',completed:true})});
 one.unmount();two.unmount();offline=false;
 const reopened=renderHook(()=>useWorkspaceStore(namespace,cloud));await waitFor(()=>expect(reopened.result.current.status).toBe('synced'));
 expect(remote.tasks[0]).toMatchObject({title:'Personal wording from tab one',completed:true});expect(reopened.result.current.pending).toBe(0);
});
