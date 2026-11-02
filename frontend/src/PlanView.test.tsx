import {webcrypto} from 'node:crypto';
import {cleanup,render,screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {PlanView,planSummary} from './PlanView';
import {createRetrieval,candidateTasks,type PlanResult} from './productTypes';
import {ASK_COPY,COPY,POLISH_COPY} from './uiCopy';
import {PRODUCT_COPY} from './productCopy';
import examples from '../public/examples.json';
import {MIGRATION_COPY,RESULT_ORDER} from './migrationCopy';
beforeEach(()=>vi.stubGlobal('crypto',webcrypto));afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals()});
function sample(){return createRetrieval({input:examples['en-general'].source,kind:'text',language:'en',result:{...structuredClone(examples['en-general'].result),demo:false,source_reviewed:false} as PlanResult})}
it('preserves exact quotations, local conditions, original input and human-review disclosure in copy',()=>{
 const row=sample(),tasks=candidateTasks(row);tasks[0].completed=true;const output=planSummary(row,tasks,'en');
 for(const evidence of row.result.evidence)expect(output).toContain(evidence.excerpt);
 for(const items of Object.values(row.result.sections))for(const item of items)for(const condition of item.source_conditions||[])expect(output).toContain(condition);
 expect(output).toContain(row.input);expect(output).toContain(PRODUCT_COPY.en.sourceUnconfirmed);expect(output).toContain('[✓]');
 row.result.review_mode='general_ask';row.result.evidence=[];expect(planSummary(row,tasks,'en')).toContain(ASK_COPY.en.warning);
});
it('offers manual copy on clipboard denial and calls print with the disclosure in printable content',async()=>{
 const user=userEvent.setup();const row=sample();row.result.review_mode='general_ask';const print=vi.spyOn(window,'print').mockImplementation(()=>{});
 Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:vi.fn(async()=>{throw new Error('denied')})}});
 const noop=()=>{};render(<PlanView row={row} tasks={candidateTasks(row)} lang="en" persistent status="Saved" onSave={noop} onRename={noop} onTask={noop} onSaveTasks={noop} onBack={noop} onEdit={noop} onCalendar={noop} onAdd={noop}/>);
 await user.click(screen.getByRole('button',{name:PRODUCT_COPY.en.copy}));expect(await screen.findByLabelText(PRODUCT_COPY.en.manualCopy)).toHaveProperty('value',planSummary(row,candidateTasks(row),'en'));
 await user.click(screen.getByRole('button',{name:PRODUCT_COPY.en.print}));expect(print).toHaveBeenCalledOnce();expect(screen.getByRole('note').textContent).toContain(ASK_COPY.en.warning);print.mockRestore();
});

it('copies retrieved Search source text with checked-source limitations',()=>{
 const row=sample();row.kind='research';row.input='How do I apply?';row.extractedOriginal='Full fetched source fixture';
 row.result.review_mode='web_research';row.result.semantic_review_complete=true;
 const text=planSummary(row,[], 'en');
 expect(text).toContain(PRODUCT_COPY.en.researchCheckedWarning);expect(text).toContain('Full fetched source fixture');
 expect(text).not.toContain(PRODUCT_COPY.en.sourceEdited);
});

it.each(['en','bn'] as const)('uses the same six-section order on screen and in copy (%s)',lang=>{
 const row=sample(),noop=()=>{},m=MIGRATION_COPY[lang];
 if(lang==='en'){
  expect(m.steps).toBe('Tasks');expect(m.documents).toBe('Required Documents');
  expect(COPY.en.steps).toBe(m.steps);expect(ASK_COPY.en.steps).toBe(m.steps);expect(COPY.en.documents).toBe(m.documents);
 }
 row.result.unknowns=[{kind:'missing',category:'fees',text:'A fee exemption is unclear.',evidence_ids:[]}];
 render(<PlanView row={row} tasks={candidateTasks(row)} lang={lang} persistent status="Saved" onSave={noop} onRename={noop} onTask={noop} onSaveTasks={noop} onBack={noop} onEdit={noop} onCalendar={noop} onAdd={noop}/>);
 const labels=[...RESULT_ORDER.map(key=>m[key]),m.others];
 expect(Array.from(document.querySelectorAll('.plan-section>h2,.plan-section>.section-heading>h2')).slice(0,6).map(node=>node.textContent)).toEqual(labels);
 const copy=planSummary(row,[],lang),positions=labels.map(label=>copy.indexOf(label+':\n'));
 expect(positions.every((position,index)=>position>=0&&(!index||position>positions[index-1]))).toBe(true);
 expect(document.querySelector('.section-others')?.textContent).toContain('A fee exemption is unclear.');
});

it('keeps empty fees and deadlines explicit without implying free or unlimited service',()=>{
 const row=sample(),noop=()=>{};row.result.sections={};row.result.unknowns=[];
 render(<PlanView row={row} tasks={[]} lang="en" persistent status="Saved" onSave={noop} onRename={noop} onTask={noop} onSaveTasks={noop} onBack={noop} onEdit={noop} onCalendar={noop} onAdd={noop}/>);
 expect(document.querySelector('.section-fees')?.textContent).toContain(MIGRATION_COPY.en.emptyFees);
 expect(document.querySelector('.section-deadlines')?.textContent).toContain(MIGRATION_COPY.en.emptyDeadlines);
 expect(planSummary(row,[],'en')).toContain(MIGRATION_COPY.en.emptyFees);
 expect(screen.getByRole('button',{name:PRODUCT_COPY.en.print})).toBeTruthy();
});

it('keeps the unreviewed disclosure once in copy and never labels unreviewed rows as web cited',()=>{
 const row=sample(),noop=()=>{};row.result.review_mode='general_ask';row.result.evidence=[];
 for(const items of Object.values(row.result.sections))for(const item of items){item.evidence_ids=[];item.support_status='unreviewed'}
 render(<PlanView row={row} tasks={candidateTasks(row)} lang="en" persistent status="Saved" onSave={noop} onRename={noop} onTask={noop} onSaveTasks={noop} onBack={noop} onEdit={noop} onCalendar={noop} onAdd={noop}/>);
 expect(document.querySelector('.plan-categories')?.children).toHaveLength(6);
 expect(Array.from(document.querySelectorAll('.support-label')).every(node=>node.textContent==='Not checked against a source')).toBe(true);
 expect(planSummary(row,[],'en').split(ASK_COPY.en.warning)).toHaveLength(2);
});

it('shares exactly the copy-plan text and keeps documents as plain text',async()=>{
 const row=sample(),tasks=candidateTasks(row),noop=()=>{},share=vi.fn(async()=>{});
 Object.defineProperty(navigator,'share',{configurable:true,value:share});
 render(<PlanView row={row} tasks={tasks} lang="en" persistent status="Saved" onSave={noop} onRename={noop} onTask={noop} onSaveTasks={noop} onBack={noop} onEdit={noop} onCalendar={noop} onAdd={noop}/>);
 await userEvent.setup().click(screen.getByRole('button',{name:PRODUCT_COPY.en.share}));
 expect(share).toHaveBeenCalledWith({text:planSummary(row,tasks,'en')});
 expect(document.querySelector('.section-documents input')).toBeNull();
 expect(document.querySelector('.step-number')).toBeNull();
 expect(Array.from(document.querySelectorAll('.plan-actions button')).map(b=>b.textContent?.trim())).toEqual([PRODUCT_COPY.en.copy,PRODUCT_COPY.en.share,PRODUCT_COPY.en.print]);
 delete (navigator as any).share;
});

it('does not warn a saved plan to save itself when starting over',async()=>{
 const row=sample(),noop=()=>{};
 render(<PlanView row={row} tasks={candidateTasks(row)} lang="en" persistent status="Saved" onSave={noop} onRename={noop} onTask={noop} onSaveTasks={noop} onBack={noop} onEdit={noop} onCalendar={noop} onAdd={noop}/>);
 await userEvent.setup().click(screen.getByRole('button',{name:COPY.en.new}));
 expect(screen.getByText(POLISH_COPY.en.newSavedPrompt)).toBeTruthy();
 expect(screen.queryByText(POLISH_COPY.en.newPrompt)).toBeNull();
});

it('keeps personal tasks inside Tasks in copied output',()=>{
 const row=sample(),task={...candidateTasks(row)[0],id:'personal',origin:null,title:'Call the office',completed:true,dueDate:'2026-11-03'};
 const output=planSummary(row,[task],'en');
 expect(output.indexOf('Call the office')).toBeGreaterThan(output.indexOf(MIGRATION_COPY.en.steps+':'));
 expect(output.indexOf('Call the office')).toBeLessThan(output.indexOf(MIGRATION_COPY.en.deadlines+':'));
 expect(output).toContain('[✓] Call the office');expect(output).toContain('2026-11-03');
 row.result.sections.steps=[];const personalOnly=planSummary(row,[task],'en').split(MIGRATION_COPY.en.steps+':')[1].split(MIGRATION_COPY.en.deadlines+':')[0];
 expect(personalOnly).toContain('Call the office');expect(personalOnly).not.toContain(MIGRATION_COPY.en.empty);
});
it('keeps the save action available and hides success when local storage has failed',async()=>{
 const row=sample(),tasks=candidateTasks(row).map(task=>({...task,saved:true})),save=vi.fn(),noop=()=>{};
 render(<PlanView row={row} tasks={tasks} lang="en" persistent status="Not saved" taskStorageError onSave={noop} onRename={noop} onTask={noop} onSaveTasks={save} onBack={noop} onEdit={noop} onCalendar={noop} onAdd={noop}/>);
 expect(screen.queryByText(PRODUCT_COPY.en.tasksSavedHelp)).toBeNull();
 const button=screen.getByRole('button',{name:PRODUCT_COPY.en.saveAll});expect(button).toHaveProperty('disabled',false);
 await userEvent.click(button);expect(save).toHaveBeenCalledOnce();
});
