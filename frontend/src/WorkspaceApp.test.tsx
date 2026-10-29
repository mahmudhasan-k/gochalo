import 'fake-indexeddb/auto';
import {webcrypto} from 'node:crypto';
import {cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {WorkspaceApp} from './WorkspaceApp';
import {MIGRATION_COPY} from './migrationCopy';
import {SOURCE_RECOVERY_COPY} from './supportPresentation';
import {PRODUCT_COPY,LOADING_COPY} from './productCopy';
import {ASK_COPY,POLISH_COPY} from './uiCopy';
import {closeLocalStore,clearWorkspace,loadWorkspace,saveWorkspace} from './localStore';
import {candidateTasks,createRetrieval,emptyData,type Operation,type ContentRecord,type PlanResult} from './productTypes';
import type {CloudStore} from './cloudStore';
import examples from '../public/examples.json';
const c=PRODUCT_COPY.en,json=(value:unknown,status=200)=>new Response(JSON.stringify(value),{status});
let result:PlanResult;
beforeEach(async()=>{
 vi.stubGlobal('crypto',webcrypto);history.replaceState(null,'','#home');localStorage.clear();await clearWorkspace('guest');
 result={...structuredClone(examples['en-general'].result),review_mode:'general_ask',demo:false,semantic_review_complete:false,evidence:[]} as PlanResult;
 vi.stubGlobal('fetch',vi.fn(async(path:string,_options:any)=>{
  if(path==='/api/session')return json({token:'offline'});
  if(path==='/api/research')return json({job_id:'plan'},202);
  if(path==='/api/analysis')return json({job_id:'plan'},202);
  if(path==='/api/extract/link')return json({job_id:'extract'},202);
  if(path==='/api/jobs/extract')return json({status:'succeeded',result:{text:'Original source',requested_url:'https://example.org',returned_url:'https://example.org/guide',retrieved_at:'2026-10-24T00:00:00Z'}});
  if(path==='/api/jobs/plan')return json({status:'succeeded',result:{...result,retrieved_source_text:'Retrieved official instructions'}});
  throw new Error('Unexpected offline request '+path);
 }));
});
afterEach(async()=>{cleanup();await new Promise(resolve=>setTimeout(resolve,20));closeLocalStore();vi.unstubAllGlobals()});
async function startQuick(){const user=userEvent.setup();await screen.findByRole('heading',{name:c.hero});await user.type(screen.getByRole('textbox',{name:c.query}),'Prepare for next week');await user.click(screen.getByRole('button',{name:c.go}));await screen.findByRole('textbox',{name:c.rename});return user}

it('offers editable extracted text after source-analysis failure and submits the chosen Text mode',async()=>{
 const user=userEvent.setup(),bodies:any[]=[];
 vi.stubGlobal('fetch',vi.fn(async(path:string,options:any)=>{
  if(path==='/api/session')return json({token:'offline'});
  if(path==='/api/extract/link')return json({job_id:'extract'},202);
  if(path==='/api/jobs/extract')return json({status:'succeeded',result:{text:'Retained original source',requested_url:'https://example.org'}});
  if(path==='/api/analysis'){bodies.push(JSON.parse(options.body));return json({job_id:'plan'+bodies.length},202)}
  if(path==='/api/jobs/plan1')return json({status:'failed',error:'review_failed'});
  if(path==='/api/jobs/plan2')return json({status:'succeeded',result});
  throw new Error(path);
 }));
 render(<WorkspaceApp initialLanguage="en"/>);
 await screen.findByRole('heading',{name:c.hero});
 await user.click(screen.getByRole('button',{name:new RegExp('^'+MIGRATION_COPY.en.link)}));
 await user.type(screen.getByRole('textbox',{name:c.url}),'https://example.org');
 await user.click(screen.getByRole('button',{name:c.go}));
 await user.click(await screen.findByRole('button',{name:SOURCE_RECOVERY_COPY.en.edit}));
 expect(screen.getByRole('textbox',{name:c.input})).toHaveProperty('value','Retained original source');
 await user.clear(screen.getByRole('textbox',{name:c.input}));await user.type(screen.getByRole('textbox',{name:c.input}),'Edited relevant passage');
 await user.click(screen.getByRole('button',{name:c.go}));await screen.findByRole('textbox',{name:c.rename});
 expect(bodies.map(b=>b.kind)).toEqual(['link','text']);expect(bodies[1].text).toBe('Edited relevant passage');
 expect(vi.mocked(fetch).mock.calls.filter(call=>call[0]==='/api/extract/link')).toHaveLength(1);
});

it('uses a search-first home and opens prepared demos without requests or saved history',async()=>{
 const user=userEvent.setup();render(<WorkspaceApp initialLanguage="en"/>);await screen.findByRole('heading',{name:c.hero});
 expect(screen.queryByRole('button',{name:c.newSearch})).toBeNull();
 await user.click(screen.getByRole('button',{name:new RegExp('^'+c.retrievals)}));expect(screen.queryByRole('button',{name:c.newSearch})).toBeNull();
 await user.click(screen.getByRole('button',{name:new RegExp('^'+c.tasks)}));expect(screen.queryByRole('button',{name:c.newSearch})).toBeNull();await user.click(screen.getByRole('button',{name:c.home}));
 expect(screen.queryByRole('button',{name:c.newSearch})).toBeNull();
 expect(screen.getByRole('button',{name:c.go})).toBeTruthy();await user.click(screen.getByRole('button',{name:/How do I apply to Harvard University from Bangladesh/}));
 expect(screen.queryByRole('button',{name:c.newSearch})).toBeNull();
 expect(screen.getByText(LOADING_COPY.en.demo[0])).toBeTruthy();
 expect(screen.getByRole('button',{name:/How do I apply to Harvard University from Bangladesh/})).toHaveProperty('disabled',true);
 expect(await screen.findByText(c.demo,{}, {timeout:4000})).toBeTruthy();expect(vi.mocked(fetch)).not.toHaveBeenCalled();
 expect((await loadWorkspace('guest')).retrievals).toEqual([]);
});
it('saves a complete plan, persists task completion, and reopens without another request',async()=>{
 const view=render(<WorkspaceApp initialLanguage="en"/>);const user=await startQuick();
 await waitFor(async()=>expect((await loadWorkspace('guest')).retrievals).toHaveLength(1));
 await user.click(screen.getByRole('button',{name:c.saveAll}));await user.click(screen.getAllByRole('checkbox')[0]);
 await user.click(screen.getByRole('button',{name:new RegExp('^'+c.tasks)}));
 await user.click(await screen.findByText('Prepare for next week',{exact:true,selector:'.task-group-title'}));await screen.findAllByRole('textbox',{name:c.taskTitle});expect(screen.getAllByRole('checkbox')[0]).toHaveProperty('checked',true);
 const input=screen.getAllByRole('textbox',{name:c.taskTitle})[0];fireEvent.change(input,{target:{value:'My personal wording'}});
 await user.click(screen.getByRole('button',{name:'Open session'}));
 expect(await screen.findByRole('textbox',{name:c.rename})).toBeTruthy();expect(screen.queryByText('My personal wording')).toBeNull();
 await waitFor(async()=>expect((await loadWorkspace('guest')).tasks[0].title).toBe('My personal wording'));
 const calls=vi.mocked(fetch).mock.calls.length;view.unmount();render(<WorkspaceApp initialLanguage="en"/>);
 await screen.findByRole('textbox',{name:c.rename});expect(vi.mocked(fetch).mock.calls).toHaveLength(calls);
});
it('uses the auto-save preference alone and keeps unsaved results out of storage until explicitly saved',async()=>{
 const user=userEvent.setup();render(<WorkspaceApp initialLanguage="en"/>);await screen.findByRole('heading',{name:c.hero});expect(screen.queryByRole('checkbox',{name:c.temporary})).toBeNull();await user.click(screen.getByRole('checkbox',{name:c.autoSave}));expect(localStorage.getItem('gochalo:auto-save')).toBe('false');
 await startQuick();expect((await loadWorkspace('guest')).retrievals).toEqual([]);
 expect(screen.getByRole('button',{name:c.saveAll})).toHaveProperty('disabled',true);
 await user.click(screen.getByRole('button',{name:c.save}));await waitFor(async()=>expect((await loadWorkspace('guest')).retrievals).toHaveLength(1));
 expect(screen.getByRole('button',{name:c.saveAll})).toHaveProperty('disabled',false);
});
it('processes a link directly, keeps source provenance, and never claims a manual check',async()=>{
 result={...structuredClone(examples['en-general'].result),demo:false,source_reviewed:false,review_mode:'ai_reviewed',semantic_review_complete:true} as PlanResult;
 const user=userEvent.setup();render(<WorkspaceApp initialLanguage="en"/>);await screen.findByRole('heading',{name:c.hero});await user.click(screen.getByRole('button',{name:new RegExp('^'+MIGRATION_COPY.en.link)}));
 await user.type(screen.getByRole('textbox',{name:c.url}),'https://example.org');await user.click(screen.getByRole('button',{name:c.go}));await screen.findByRole('textbox',{name:c.rename});
 await user.click(screen.getByText(c.sources,{exact:true,selector:'summary'}));expect(screen.getByText(c.sourceUnconfirmed,{selector:'.source-panel p'})).toBeTruthy();expect(screen.getByText('Original source',{selector:'.source-panel pre'})).toBeTruthy();
 const body=vi.mocked(fetch).mock.calls.find(([path])=>path==='/api/analysis')?.[1]?.body;expect(JSON.parse(body as string).reviewed).toBe(false);
 expect(screen.queryByRole('checkbox',{name:/checked this text/})).toBeNull();
});
it('uses the preserved old General Ask backend from central Search',async()=>{
 const user=userEvent.setup();render(<WorkspaceApp initialLanguage="en"/>);await screen.findByRole('heading',{name:c.hero});
 await user.type(screen.getByRole('textbox',{name:c.query}),'Prepare for a trip');await user.click(screen.getByRole('button',{name:c.go}));
 await screen.findByRole('textbox',{name:c.rename});
 const calls=vi.mocked(fetch).mock.calls;expect(calls.some(([path])=>path==='/api/research')).toBe(false);
 const body=JSON.parse(calls.find(([path])=>path==='/api/analysis')![1]!.body as string);
 expect(body).toMatchObject({kind:'ask',text:'Prepare for a trip',language:'en'});
 expect(screen.getAllByText(ASK_COPY.en.warning).length).toBeGreaterThan(0);
 const stored=(await loadWorkspace('guest')).retrievals[0];expect(stored.kind).toBe('ask');expect(stored.extractedOriginal).toBe('');
});
it('automatically migrates guest history after sign-in without a confirmation dialog',async()=>{
 const row=createRetrieval({title:'Guest plan',input:'Guest query',kind:'ask',language:'en',result});await saveWorkspace('guest',{...emptyData(),retrievals:[row],tasks:candidateTasks(row)});
 const remote=emptyData();const cloud:CloudStore={pull:vi.fn(async()=>structuredClone(remote)),apply:vi.fn(async(op:Operation)=>{const rows=remote[op.table] as ContentRecord[];const record={...op.patch,revision:1} as ContentRecord;rows.push(record);return record})};
 render(<WorkspaceApp initialLanguage="en" account={{id:'fixture-account',name:'Test person',cloud,signOut:vi.fn()}}/>);
 await waitFor(()=>expect(cloud.apply).toHaveBeenCalled());expect(screen.queryByRole('dialog',{name:c.importTitle})).toBeNull();
 await waitFor(async()=>expect((await loadWorkspace('guest')).retrievals).toEqual([]));expect(remote.retrievals[0].id).toBe(row.id);
});
it('deletes a retrieval and its linked tasks after explicit confirmation',async()=>{
 const user=userEvent.setup();render(<WorkspaceApp initialLanguage="en"/>);await startQuick();await user.click(screen.getByRole('button',{name:c.saveAll}));await user.click(screen.getByRole('button',{name:new RegExp('^'+c.retrievals)}));
 await user.click(screen.getByRole('button',{name:c.delete+': Prepare for next week'}));await user.click(screen.getByRole('button',{name:c.confirmDelete}));
 expect(await screen.findByText(c.emptyRetrievals)).toBeTruthy();await user.click(screen.getByRole('button',{name:new RegExp('^'+c.tasks)}));expect(await screen.findByText(c.emptyTasks)).toBeTruthy();
});
it('adds personal tasks with stable IDs and previews dates before calendar export',async()=>{
 const user=userEvent.setup();render(<WorkspaceApp initialLanguage="en"/>);await startQuick();
 await user.type(screen.getByRole('textbox',{name:c.taskTitle}),'Call the office');await user.click(screen.getByRole('button',{name:c.add}));
 await user.click(screen.getByRole('button',{name:new RegExp('^'+c.tasks)}));await user.click(await screen.findByText('Prepare for next week',{exact:true,selector:'.task-group-title'}));const title=await screen.findByRole('textbox',{name:c.taskTitle});expect(title).toHaveProperty('value','Call the office');
 const group=title.closest('details')!;expect(group.open).toBe(true);await user.click(within(group).getByText('Prepare for next week',{exact:true}));expect(group.open).toBe(false);await user.click(within(group).getByText('Prepare for next week',{exact:true}));expect(group.open).toBe(true);
 const date=screen.getByLabelText(c.due);fireEvent.change(date,{target:{value:'2026-11-02'}});fireEvent.change(screen.getByLabelText(c.time),{target:{value:'08:57'}});fireEvent.change(screen.getByLabelText(c.timezone),{target:{value:'UTC'}});
 await user.click(screen.getByRole('button',{name:c.calendar}));const dialog=await screen.findByRole('dialog',{name:c.calendarTitle});
 expect(within(dialog).getByLabelText(c.date)).toHaveProperty('value','2026-11-02');expect(within(dialog).getByLabelText(c.time)).toHaveProperty('value','08:57');expect(within(dialog).getByLabelText(c.timezone)).toHaveProperty('value','UTC');expect(within(dialog).getByRole('button',{name:c.download})).toHaveProperty('disabled',false);
 const data=await loadWorkspace('guest');const personal=data.tasks.find(task=>task.origin===null)!;expect(personal.id).toBe(title.id);expect(personal.saved).toBe(true);expect(personal.dueTime).toBe('08:57');expect(personal.dueTimezone).toBe('UTC');
});
it('keeps a result usable and discloses storage denial',async()=>{
 const database=globalThis.indexedDB;closeLocalStore();vi.stubGlobal('indexedDB',undefined);
 render(<WorkspaceApp initialLanguage="en"/>);await startQuick();expect(screen.getAllByText(c.unsaved).length).toBeGreaterThan(0);expect(screen.getByRole('button',{name:c.copy})).toBeTruthy();
 vi.stubGlobal('indexedDB',database);
});

it('defaults to English and light, and localizes both navigation counts from the language dropdown',async()=>{
 const row=createRetrieval({title:'Saved session',input:'Query',kind:'ask',language:'en',result});
 const tasks=candidateTasks(row).map(task=>({...task,saved:true}));
 await saveWorkspace('guest',{...emptyData(),retrievals:[row],tasks});
 const user=userEvent.setup();render(<WorkspaceApp/>);
 await screen.findByRole('heading',{name:c.hero});expect(document.documentElement.classList.contains('dark')).toBe(false);
 expect(screen.getByRole('button',{name:/^Language:/}).textContent).toContain('English');
 expect(screen.getByRole('button',{name:new RegExp('^'+c.retrievals)}).querySelector('.nav-count')?.textContent).toBe('1');
 await user.click(screen.getByRole('button',{name:/^Language:/}));await user.click(screen.getByRole('menuitemradio',{name:'বাংলা'}));
 const bn=PRODUCT_COPY.bn;
 expect(screen.getByRole('button',{name:new RegExp('^'+bn.retrievals)}).querySelector('.nav-count')?.textContent).toBe('১');
 expect(screen.getByRole('button',{name:new RegExp('^'+bn.tasks)}).querySelector('.nav-count')?.textContent).toBe(tasks.length.toLocaleString('bn-BD'));
 expect(screen.getByRole('button',{name:/^ভাষা:/}).textContent).toContain('বাংলা');
});

it('keeps the account usable when sign-out fails and clears its cache only after success',async()=>{
 const row=createRetrieval({input:'Sign-out fixture',kind:'ask',language:'en',result});const remote={...emptyData(),retrievals:[{...row,revision:1}]};
 const cloud:CloudStore={pull:vi.fn(async()=>structuredClone(remote)),apply:vi.fn()};const signOut=vi.fn().mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce(undefined);
 const user=userEvent.setup();render(<WorkspaceApp account={{id:'signout-fixture',name:'Test person',cloud,signOut}}/>);
 await waitFor(async()=>expect((await loadWorkspace('account:signout-fixture')).retrievals).toHaveLength(1));
 await user.click(screen.getByRole('button',{name:c.account+': Test person'}));await user.click(screen.getByRole('button',{name:c.signOut}));
 await waitFor(()=>expect(signOut).toHaveBeenCalledTimes(1));expect((await loadWorkspace('account:signout-fixture')).retrievals).toHaveLength(1);
 const error=screen.getAllByRole('dialog').find(dialog=>within(dialog).queryByText(c.error))!;await user.click(within(error).getByRole('button',{name:c.cancel}));
 await user.click(screen.getByRole('button',{name:c.account+': Test person'}));await user.click(screen.getByRole('button',{name:c.signOut}));await waitFor(async()=>expect((await loadWorkspace('account:signout-fixture')).retrievals).toEqual([]));
});

it('requires an explicit retry or discard before signing out with unsynced work',async()=>{
 const row=createRetrieval({input:'Pending sign-out fixture',kind:'ask',language:'en',result});const remote={...emptyData(),retrievals:[{...row,revision:1}]};
 const cloud:CloudStore={pull:vi.fn(async()=>structuredClone(remote)),apply:vi.fn(async()=>{throw new Error('offline')})};const signOut=vi.fn(async()=>{}),user=userEvent.setup();
 history.replaceState(null,'','#retrieval/'+row.id);render(<WorkspaceApp account={{id:'pending-signout-fixture',name:'Test person',cloud,signOut}}/>);
 await screen.findByRole('textbox',{name:c.rename});await user.type(screen.getByRole('textbox',{name:c.taskTitle}),'Pending personal task');await user.click(screen.getByRole('button',{name:c.add}));
 await waitFor(()=>expect(cloud.apply).toHaveBeenCalled());await user.click(screen.getByRole('button',{name:c.account+': Test person'}));await user.click(screen.getByRole('button',{name:c.signOut}));
 const dialog=await screen.findByRole('dialog',{name:c.signOut});expect(signOut).not.toHaveBeenCalled();
 await user.click(within(dialog).getByRole('button',{name:c.cancel}));expect((await loadWorkspace('account:pending-signout-fixture')).outbox.length).toBeGreaterThan(0);
 await user.click(screen.getByRole('button',{name:c.account+': Test person'}));await user.click(screen.getByRole('button',{name:c.signOut}));const again=await screen.findByRole('dialog',{name:c.signOut});await user.click(within(again).getByRole('button',{name:c.discard}));
 await waitFor(()=>expect(signOut).toHaveBeenCalledOnce());await waitFor(async()=>expect(await loadWorkspace('account:pending-signout-fixture')).toEqual(emptyData()));
});

it('submits Ask with Enter once, retaining Shift+Enter and ignoring IME and repeated keydown',async()=>{
 const user=userEvent.setup();render(<WorkspaceApp/>);await screen.findByRole('heading',{name:c.hero});
 const query=screen.getByRole('textbox',{name:c.query});await user.type(query,'Make a plan');
 await user.keyboard('{Shift>}{Enter}{/Shift}');expect(query).toHaveProperty('value','Make a plan\n');
 fireEvent.keyDown(query,{key:'Enter',isComposing:true});fireEvent.keyDown(query,{key:'Enter',repeat:true});
 expect(vi.mocked(fetch).mock.calls.some(([path])=>path==='/api/analysis')).toBe(false);
 fireEvent.keyDown(query,{key:'Enter'});fireEvent.keyDown(query,{key:'Enter'});
 await screen.findByRole('textbox',{name:c.rename});
 const calls=vi.mocked(fetch).mock.calls.filter(([path])=>path==='/api/analysis');expect(calls).toHaveLength(1);
 expect(JSON.parse(calls[0][1]!.body as string)).toMatchObject({kind:'ask',text:'Make a plan\n'});
});
it('keeps paste-text Enter multiline and ignores an empty Ask submission',async()=>{
 const user=userEvent.setup();render(<WorkspaceApp/>);await screen.findByRole('heading',{name:c.hero});
 await user.click(screen.getByRole('textbox',{name:c.query}));await user.keyboard('{Enter}');expect(fetch).not.toHaveBeenCalled();
 await user.click(screen.getByRole('button',{name:new RegExp('^'+MIGRATION_COPY.en.text)}));const input=screen.getByRole('textbox',{name:c.input});await user.type(input,'First{Enter}Second');
 expect(input).toHaveProperty('value','First\nSecond');expect(fetch).not.toHaveBeenCalled();
});
it('resets one checklist without changing saved tasks, wording or schedules',async()=>{
 const row=createRetrieval({title:'Reset fixture',input:'Query',kind:'ask',language:'en',result});
 const tasks=candidateTasks(row).map(task=>({...task,saved:true,completed:true,dueDate:'2026-11-03',title:'Personal '+task.title}));
 await saveWorkspace('guest',{...emptyData(),retrievals:[row],tasks});history.replaceState(null,'','#retrieval/'+row.id);
 const user=userEvent.setup();render(<WorkspaceApp/>);await screen.findByRole('textbox',{name:c.rename});
 const section=screen.getByRole('heading',{name:MIGRATION_COPY.en.steps}).closest('section')!;
 expect(section.querySelector('.step-number')).toBeNull();
 expect(within(section).getByRole('progressbar').getAttribute('aria-valuenow')).toBe(String(result.sections.steps.length));
 await user.click(within(section).getByRole('button',{name:POLISH_COPY.en.reset}));
 await waitFor(async()=>{const data=await loadWorkspace('guest');expect(data.tasks.filter(task=>task.origin?.startsWith('steps:')).every(task=>!task.completed)).toBe(true)});
 const data=await loadWorkspace('guest');expect(data.tasks.filter(task=>task.origin?.startsWith('documents:')).every(task=>task.completed)).toBe(true);
 expect(data.tasks.every(task=>task.saved&&task.dueDate==='2026-11-03'&&task.title.startsWith('Personal '))).toBe(true);
});
it('renames history inline, cancels edits, and switches Home panels without navigation',async()=>{
 const row=createRetrieval({title:'Original session',input:'Query',kind:'ask',language:'en',result});const tasks=candidateTasks(row).map(task=>({...task,saved:true}));
 await saveWorkspace('guest',{...emptyData(),retrievals:[row],tasks});const user=userEvent.setup();render(<WorkspaceApp/>);await screen.findByRole('heading',{name:c.hero});
 const recent=screen.getByRole('button',{name:POLISH_COPY.en.recent+' (1)'}),saved=screen.getByRole('button',{name:POLISH_COPY.en.savedTasks+' ('+tasks.length+')'});
 expect(recent.getAttribute('aria-pressed')).toBe('true');await user.click(saved);expect(saved.getAttribute('aria-pressed')).toBe('true');expect(location.hash).toBe('#home');await user.click(recent);
 await user.click(screen.getByRole('button',{name:c.rename+': Original session'}));const title=screen.getByRole('textbox',{name:c.rename});await user.clear(title);await user.type(title,'Edited session{Enter}');
 await waitFor(async()=>expect((await loadWorkspace('guest')).retrievals[0].title).toBe('Edited session'));
 await user.click(screen.getByRole('button',{name:c.rename+': Edited session'}));await user.type(screen.getByRole('textbox',{name:c.rename}),' discarded{Escape}');expect(screen.queryByRole('textbox',{name:c.rename})).toBeNull();
 expect((await loadWorkspace('guest')).retrievals[0].title).toBe('Edited session');
});
it('keeps task group completion totals independent of filtering and collapse stable across edits',async()=>{
 const row=createRetrieval({title:'Grouped session',input:'Query',kind:'ask',language:'en',result});const tasks=candidateTasks(row).map((task,i)=>({...task,saved:true,completed:i===0}));
 await saveWorkspace('guest',{...emptyData(),retrievals:[row],tasks});history.replaceState(null,'','#tasks');const user=userEvent.setup();render(<WorkspaceApp/>);
 const summary=await screen.findByText(row.title,{exact:true,selector:'.task-group-title'});const group=summary.closest('details')!;expect(group.open).toBe(false);await user.click(summary);await screen.findAllByRole('textbox',{name:c.taskTitle});
 await user.click(screen.getByRole('button',{name:c.open}));expect(group.querySelector('.completion-badge')?.textContent).toBe('1/'+tasks.length);
 await user.click(within(group).getByText(row.title,{exact:true}));expect(group.open).toBe(false);
 await user.click(screen.getByRole('button',{name:c.all}));expect(group.open).toBe(false);
});

it('offers only three secondary cards, toggles each back to Ask, and preserves mode drafts',async()=>{
 const user=userEvent.setup();render(<WorkspaceApp/>);await screen.findByRole('heading',{name:c.hero});
 const grid=document.querySelector('.feature-grid')!;
 expect(within(grid as HTMLElement).getAllByRole('button')).toHaveLength(3);
 expect(within(grid as HTMLElement).queryByRole('button',{name:c.quick})).toBeNull();
 await user.type(screen.getByRole('textbox',{name:c.query}),'My Ask draft');
 for(const name of [MIGRATION_COPY.en.photo,MIGRATION_COPY.en.link,MIGRATION_COPY.en.text]){
  const card=within(grid as HTMLElement).getByRole('button',{name:new RegExp('^'+name)});
  await user.click(card);expect(card.getAttribute('aria-pressed')).toBe('true');
  expect(grid.querySelectorAll('.selected')).toHaveLength(1);
  await user.click(card);expect(grid.querySelectorAll('.selected')).toHaveLength(0);
  expect(screen.getByRole('textbox',{name:c.query})).toHaveProperty('value','My Ask draft');
 }
 await user.click(within(grid as HTMLElement).getByRole('button',{name:new RegExp('^'+MIGRATION_COPY.en.text)}));
 await user.type(screen.getByRole('textbox',{name:c.input}),'My text draft');
 await user.click(within(document.querySelector('.composer-head')! as HTMLElement).getByRole('button',{name:c.backToSearch}));
 expect(grid.querySelectorAll('.selected')).toHaveLength(0);
 expect(screen.getByRole('textbox',{name:c.query})).toHaveProperty('value','My Ask draft');
 await user.click(within(grid as HTMLElement).getByRole('button',{name:new RegExp('^'+MIGRATION_COPY.en.text)}));
 expect(screen.getByRole('textbox',{name:c.input})).toHaveProperty('value','My text draft');
 expect(fetch).not.toHaveBeenCalled();
});

it('opens an anchored account panel with icon-only trigger and restores focus on Escape',async()=>{
 const cloud:CloudStore={pull:vi.fn(async()=>emptyData()),apply:vi.fn()};
 const user=userEvent.setup();render(<WorkspaceApp account={{id:'popover-fixture',name:'Test person',cloud,signOut:vi.fn()}}/>);
 const trigger=await screen.findByRole('button',{name:c.account+': Test person'});
 expect(trigger.textContent).toBe('');await user.click(trigger);
 const panel=screen.getByRole('dialog',{name:c.account});
 expect(panel.closest('.account-control')).toBeTruthy();expect(panel.tagName).toBe('DIV');
 expect(panel.querySelector('.account-identity')?.textContent).toContain('Test person');
 await user.keyboard('{Escape}');expect(screen.queryByRole('dialog',{name:c.account})).toBeNull();expect(document.activeElement).toBe(trigger);
 await user.click(trigger);await user.click(screen.getByRole('heading',{name:c.hero}));
 expect(screen.queryByRole('dialog',{name:c.account})).toBeNull();
});

it('keeps a failed old-backend Ask draft without trying web Search',async()=>{
 const normal=vi.mocked(fetch).getMockImplementation()!;
 vi.mocked(fetch).mockImplementation((path:any,options:any)=>path==='/api/analysis'?Promise.resolve(json({detail:'analysis_paused'},503)):normal(path,options));
 const user=userEvent.setup();render(<WorkspaceApp/>);await screen.findByRole('heading',{name:c.hero});
 await user.type(screen.getByRole('textbox',{name:c.query}),'How to buy a railway ticket?');
 await user.click(screen.getByRole('button',{name:c.go}));expect(await screen.findByRole('alert')).toBeTruthy();
 expect(screen.getByRole('textbox',{name:c.query})).toHaveProperty('value','How to buy a railway ticket?');
 expect(vi.mocked(fetch).mock.calls.some(([path])=>path==='/api/research')).toBe(false);
});

it('links to the public GitHub repository safely in a new tab',()=>{render(<WorkspaceApp/>);const link=screen.getByRole('link',{name:'GitHub (opens in a new tab)'});expect(link.getAttribute('href')).toBe('https://github.com/mahmudhasan-k/gochalo');expect(link.getAttribute('target')).toBe('_blank');expect(link.getAttribute('rel')).toContain('noopener')});
