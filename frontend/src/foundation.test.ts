import 'fake-indexeddb/auto';
import {webcrypto} from 'node:crypto';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {buildCalendar,explicitDate} from './calendar';
import {clearWorkspace,closeLocalStore,legacyCompletion,loadWorkspace,saveWorkspace} from './localStore';
import {mergePending} from './cloudStore';
import {candidateTasks,taskOrder,createRetrieval,emptyData,type Operation,type PlanResult} from './productTypes';
import examples from '../public/examples.json';

beforeEach(()=>{vi.stubGlobal('crypto',webcrypto);localStorage.clear()});
afterEach(async()=>{await clearWorkspace('guest');await clearWorkspace('account:one');closeLocalStore();vi.unstubAllGlobals()});
function retrieval(){return createRetrieval({input:'Plan my week',kind:'ask',language:'en',result:{...structuredClone(examples['en-general'].result),review_mode:'general_ask'} as PlanResult})}

it('keeps guest and account snapshots isolated across reload and clear',async()=>{
 const row=retrieval(),tasks=candidateTasks(row);const data={...emptyData(),retrievals:[row],tasks};
 await saveWorkspace('guest',data);await saveWorkspace('account:one',{...emptyData(),retrievals:[{...row,title:'Account'}]});
 closeLocalStore();expect(await loadWorkspace('guest')).toEqual(data);
 expect((await loadWorkspace('account:one')).retrievals[0].title).toBe('Account');
 await clearWorkspace('account:one');expect(await loadWorkspace('account:one')).toEqual(emptyData());
 expect((await loadWorkspace('guest')).retrievals[0].title).toBe(row.title);
 expect(JSON.stringify(data)).not.toMatch(/token|imageBytes/);
});
it('reports unavailable storage without deleting an existing snapshot',async()=>{
 const row=retrieval();await saveWorkspace('guest',{...emptyData(),retrievals:[row]});closeLocalStore();
 const database=globalThis.indexedDB;vi.stubGlobal('indexedDB',undefined);
 await expect(loadWorkspace('guest')).rejects.toThrow('storage_unavailable');
 vi.stubGlobal('indexedDB',database);expect((await loadWorkspace('guest')).retrievals[0].id).toBe(row.id);
});
it('restores only matching legacy flags without manufacturing history',async()=>{
 const row=retrieval();const digest=await webcrypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify({result:row.result,source:row.input,language:row.language})));
 const key='shobuj-checklist-v1:'+Array.from(new Uint8Array(digest),v=>v.toString(16).padStart(2,'0')).join('');
 localStorage.setItem(key,JSON.stringify({checked:['steps:0']}));expect(await legacyCompletion(row)).toEqual(new Set(['steps:0']));
 expect(await loadWorkspace('guest')).toEqual(emptyData());
});
it('keeps task edits separate from the original evidence and uses stable origin identifiers',()=>{
 const row=retrieval(),original=structuredClone(row.result),tasks=candidateTasks(row);
 tasks[0].title='My personal wording';tasks[0].saved=true;tasks[0].completed=true;
 expect(row.result).toEqual(original);expect(tasks[0].origin).toBe('steps:0');
 expect(new Set(tasks.map(task=>task.id)).size).toBe(tasks.length);
});
it('rebases only local changed fields and never resurrects server deletions',()=>{
 const row=retrieval(),task=candidateTasks(row)[0];task.title='Server title';task.revision=2;
 const operation:Operation={id:'operation',table:'tasks',recordId:task.id,baseRevision:1,createdAt:row.createdAt,patch:{completed:true}};
 const remote={...emptyData(),retrievals:[row],tasks:[task]};
 const merged=mergePending(remote,[operation]);expect(merged.tasks[0]).toMatchObject({title:'Server title',completed:true,revision:2});
 expect(remote.tasks[0].completed).toBe(false);
 remote.retrievals[0].deleted=true;expect(mergePending(remote,[operation]).tasks[0].deleted).toBe(true);
 remote.tasks[0].deleted=true;expect(mergePending(remote,[{...operation,patch:{deleted:false}}]).tasks[0].deleted).toBe(true);
});
it('exports valid all-day boundaries, escaping, UTF-8 folding and stable event identity',()=>{
 const entry={id:'stable',title:'পরিকল্পনা, কাজ; আবার\\নতুন',date:'2026-12-31',timezone:'Asia/Dhaka',description:'First\nSecond'};
 const first=buildCalendar([entry],new Date('2026-10-24T00:00:00Z'));
 expect(first).toContain('UID:stable@gochalo');expect(first).toContain('DTSTART;VALUE=DATE:20261231\r\nDTEND;VALUE=DATE:20270101');
 expect(first).toContain('\\,');expect(first).toContain('\\;');expect(first).toContain('DESCRIPTION:First\\nSecond');
 expect(buildCalendar([entry],new Date('2026-10-25T00:00:00Z'))).toContain('UID:stable@gochalo');
 const long=buildCalendar([{...entry,title:'ক'.repeat(100)}]);expect(long.split('\r\n').every(line=>new TextEncoder().encode(line).length<=75)).toBe(true);
});
it('requires exact valid dates and converts explicitly chosen Bangladesh time',()=>{
 expect(explicitDate('শেষ দিন ২০২৬-১১-০২')).toBe('2026-11-02');
 expect(explicitDate('within 30 days')).toBe('');expect(explicitDate('November 2')).toBe('');expect(explicitDate('2026-02-30')).toBe('');
 const entry={id:'a',title:'Appointment',date:'2026-11-02',time:'10:00',timezone:'Asia/Dhaka'};
 expect(buildCalendar([entry])).toContain('DTSTART:20261102T040000Z\r\nDTEND:20261102T043000Z');
 expect(()=>buildCalendar([{...entry,timezone:'unknown'}])).toThrow('calendar_timezone');
 expect(()=>buildCalendar([{...entry,date:'2026-02-30'}])).toThrow('calendar_invalid');
});

it('keeps generated task order after a cloud pull returns UUID-sorted records',()=>{
 const tasks=candidateTasks(retrieval());const expected=tasks.map(task=>task.origin);
 expect([...tasks].reverse().sort(taskOrder).map(task=>task.origin)).toEqual(expected);
});

it('escapes all newline forms so titles cannot introduce calendar fields',()=>{
 const calendar=buildCalendar([{id:'stable',title:'Bangla বাংলা\rInjected: field\r\nNext\nLine',date:'2026-11-02',timezone:'UTC'}]);
 expect(calendar).toContain('SUMMARY:Bangla বাংলা\\nInjected: field\\nNext\\nLine');
 expect(calendar.split('BEGIN:VEVENT')).toHaveLength(2);
});
