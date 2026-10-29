import {beforeEach,afterEach,it,expect,vi} from 'vitest';
import {render,screen,fireEvent,cleanup,waitFor} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {App} from '../legacy/LegacyJourney';
import {ASK_COPY,COPY} from './uiCopy';
const question='How can I organize a student bank-account application?';
const plan={review_mode:'general_ask',semantic_review_complete:false,has_guidance:true,demo:false,partial:false,withheld_count:0,
 sections:{explanation:[{text:'Prepare a general application plan.',evidence_ids:[]}],steps:[{text:'Check the bank’s current account requirements.',evidence_ids:[]}],documents:[{text:'Check which student records the bank accepts.',evidence_ids:[]}],fees:[],deadlines:[]},evidence:[],
 unknowns:[{kind:'unverified',category:'fees',reason_code:'incomplete_review',text:'Confirm the current fee with the bank.',evidence_ids:[]}]};
let fail=false;let bodies:any[]=[];
beforeEach(()=>{fail=false;bodies=[];vi.stubGlobal('fetch',vi.fn(async(url:unknown,options?:RequestInit)=>{
 const path=String(url);
 if(path.endsWith('/api/health'))return new Response(JSON.stringify({status:'ok'}));
 if(path.endsWith('/api/session'))return new Response(JSON.stringify({token:'offline-token'}));
 if(path.endsWith('/api/analysis')){bodies.push(JSON.parse(String(options?.body)));return new Response(JSON.stringify({job_id:'ask-job'}),{status:202})}
 if(path.includes('/api/jobs/'))return new Response(JSON.stringify(fail?{status:'failed',error:'timeout'}:{status:'succeeded',result:plan}));
 throw new Error('Unexpected mocked request');
}));localStorage.clear()});
afterEach(()=>{cleanup();vi.unstubAllGlobals()});
async function start(){const user=userEvent.setup();const view=render(<App/>);await user.click(screen.getByRole('button',{name:'English'}));await user.click(screen.getByRole('button',{name:ASK_COPY.en.tab}));fireEvent.change(screen.getByLabelText(ASK_COPY.en.input),{target:{value:question}});return {user,...view}}
it('submits a question without notice confirmation and shows checklists plus an explicit plan badge',async()=>{
 const {user,container}=await start();expect(screen.queryByRole('checkbox')).toBeNull();
 await user.click(screen.getByRole('button',{name:ASK_COPY.en.submit}));
 await screen.findByRole('heading',{name:ASK_COPY.en.title});
 expect(bodies).toHaveLength(1);expect(bodies[0]).toMatchObject({kind:'ask',text:question,language:'en'});expect(bodies[0].reviewed).toBeUndefined();
 expect(screen.getByText(ASK_COPY.en.badge)).toBeTruthy();expect(container.querySelector('.ask-warning')?.textContent).toContain(ASK_COPY.en.warning);
 await waitFor(()=>expect(screen.getAllByRole('checkbox').every(c=>!(c as HTMLInputElement).disabled)).toBe(true));
 expect(container.querySelectorAll('.evidence')).toHaveLength(0);
 expect(container.querySelector('.print-evidence')?.textContent).toContain(ASK_COPY.en.question);
 expect(container.querySelector('.print-evidence')?.textContent).toContain(question);
 expect(container.querySelector('#print-help')?.textContent).toBe(ASK_COPY.en.printHelp);
 expect(container.querySelector('.ask-warning')?.closest('.export-options')).toBeNull();
});
it('copies current checklist flags with the unreviewed-plan disclosure and original question',async()=>{
 const {user}=await start();await user.click(screen.getByRole('button',{name:ASK_COPY.en.submit}));await screen.findByRole('heading',{name:ASK_COPY.en.title});
 const clipboard=vi.spyOn(navigator.clipboard,'writeText').mockResolvedValue();
 const checkbox=screen.getByRole('checkbox',{name:plan.sections.steps[0].text});await waitFor(()=>expect((checkbox as HTMLInputElement).disabled).toBe(false));await user.click(checkbox);
 await user.click(screen.getByRole('button',{name:COPY.en.copy}));
 const text=clipboard.mock.calls[0][0];expect(text).toContain(ASK_COPY.en.warning);expect(text).toContain(question);expect(text).toContain('[✓] '+plan.sections.steps[0].text);expect(text).not.toContain(COPY.en.evidence);
});
it('keeps question and text drafts separate and shows bilingual Ask copy',async()=>{
 const {user}=await start();await user.click(screen.getByRole('button',{name:COPY.en.text}));
 fireEvent.change(screen.getByLabelText(COPY.en.paste),{target:{value:'A separate notice draft.'}});
 await user.click(screen.getByRole('button',{name:ASK_COPY.en.tab}));expect((screen.getByLabelText(ASK_COPY.en.input) as HTMLTextAreaElement).value).toBe(question);
 await user.click(screen.getByRole('button',{name:'বাংলা'}));expect(screen.getByRole('button',{name:ASK_COPY.bn.tab})).toBeTruthy();expect(screen.getByRole('button',{name:ASK_COPY.bn.submit})).toBeTruthy();
});
it('limits Ask to 2000 characters and keeps the draft after a planning failure',async()=>{
 const {user}=await start();expect(screen.getByLabelText(ASK_COPY.en.input).getAttribute('maxlength')).toBe('2000');
 fireEvent.change(screen.getByLabelText(ASK_COPY.en.input),{target:{value:'x'.repeat(2001)}});expect((screen.getByRole('button',{name:ASK_COPY.en.submit}) as HTMLButtonElement).disabled).toBe(true);
 fireEvent.change(screen.getByLabelText(ASK_COPY.en.input),{target:{value:question}});fail=true;
 await user.click(screen.getByRole('button',{name:ASK_COPY.en.submit}));await screen.findByRole('alert');expect((screen.getByLabelText(ASK_COPY.en.input) as HTMLTextAreaElement).value).toBe(question);expect(bodies).toHaveLength(1);
});
