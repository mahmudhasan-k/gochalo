import {COPY,JOURNEY_COPY} from './uiCopy';
import {afterEach,beforeEach,describe,it,expect,vi} from 'vitest';
import {render,screen,cleanup,waitFor,fireEvent} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {App} from '../legacy/LegacyJourney';
import examples from '../public/examples.json';
const example=examples['en-general'];
let outcome='success';
let extract=false;
let clipboard='';
let reportedUrl='https://example.gov.bd/b';
beforeEach(()=>{
 outcome='success';extract=false;clipboard='';reportedUrl='https://example.gov.bd/b';
 vi.stubGlobal('fetch',vi.fn(async(input:unknown)=>{
 const path=String(input);
 if(path.endsWith('/api/health'))return new Response(JSON.stringify({status:'ok'}));
 if(path.includes('examples.json'))return new Response(JSON.stringify(examples));
 if(path.includes('/api/extract/image')&&outcome.startsWith('image_'))return new Response(JSON.stringify({detail:outcome}),{status:400});
 if(path.includes('/api/session'))return new Response(JSON.stringify({token:'test-token'}));
 if(path.includes('/api/requests/'))return new Response(JSON.stringify({job_id:'test-job'}));
 if(path.includes('/api/analysis')&&outcome==='lost-submission')throw new TypeError('Failed to fetch');
 if(path.includes('/api/extract/link')&&outcome.startsWith('link-error:'))return new Response(JSON.stringify({detail:outcome.split(':')[1]}),{status:400});
 if(path.includes('/api/analysis')&&outcome==='capacity')return new Response(JSON.stringify({detail:'job_capacity'}),{status:503});
 if(path.includes('/api/jobs/')&&outcome==='disconnected')throw new TypeError('Failed to fetch');
 if(path.includes('/api/jobs/')&&outcome==='expired')return new Response(JSON.stringify({detail:'job_not_found'}),{status:404});
 if(path.includes('/api/jobs/'))return new Response(JSON.stringify(['failed','review-failed','malformed-analysis'].includes(outcome)?{status:'failed',stage:'analyzing',error:outcome==='review-failed'?'review_failed':outcome==='malformed-analysis'?'malformed_response':'service_busy'}:{status:'succeeded',stage:'done',result:extract?{text:'Only students may apply. Fee 100 taka.',requested_url:'https://example.gov.bd/a',returned_url:reportedUrl,retrieved_at:'2026-10-23T04:00:00Z'}:{...example.result,demo:false,...(outcome==='uncertainties'?{unknowns:[{kind:'missing',text:'The passage gives no fee.',evidence_ids:[]},{kind:'contradiction',text:'The two dates differ.',evidence_ids:['e1','e4']},{kind:'unverified',text:'Applicability could not be established.',evidence_ids:[]}]}:{}),...(outcome==='attached-context'?{sections:{...example.result.sections,steps:[{text:'Submit the form.',evidence_ids:['e1'],source_conditions:['Only current students who live in this district may apply.']}]}}:{}),...(outcome==='section-states'?{sections:{...example.result.sections,documents:[],fees:[]},section_states:{documents:'unconfirmed',fees:'not_stated',steps:'partial'},unknowns:[{kind:'unverified',category:'documents',reason_code:'unresolved_scope',text:'Document conditions remain unclear.',evidence_ids:[]},{kind:'missing',category:'fees',reason_code:'source_absent',text:'Fee details are not stated.',evidence_ids:[]}]}:{}),...(outcome==='noguidance'?{has_guidance:false,partial:true,sections:{explanation:[],steps:[],documents:[],fees:[],deadlines:[]}}:{})}}));
 return new Response(JSON.stringify({job_id:'test-job'}),{status:202});
 }));
});
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.unstubAllEnvs()});

it('shows link retrieval time beside provenance during bilingual review and retains it in result/copy/print',async()=>{
 const user=userEvent.setup();const {container}=render(<App/>);extract=true;
 await user.click(screen.getByRole('button',{name:'English'}));
 await user.click(screen.getByRole('button',{name:COPY.en.link}));await user.type(screen.getByLabelText('Public page URL'),'https://example.gov.bd/a');
 await user.click(screen.getByRole('button',{name:'Read the linked page'}));
 await screen.findByRole('heading',{name:'This is the text we will explain'});
 expect(container.querySelector('.source-provenance time')?.getAttribute('datetime')).toBe('2026-10-23T04:00:00Z');
 expect(screen.getByText(/Retrieved:/).textContent).toContain('23/10/2026');
 expect(screen.getByText(/Requested URL:/)).toBeTruthy();
 await user.click(screen.getByRole('button',{name:'বাংলা'}));
 expect(screen.getByText(/লেখা নেওয়া হয়েছে:/)).toBeTruthy();
 expect(container.querySelector('time')?.getAttribute('datetime')).toBe('2026-10-23T04:00:00Z');
 await user.click(screen.getByRole('button',{name:'English'}));
 extract=false;await user.click(screen.getByRole('checkbox'));
 await user.click(screen.getByRole('button',{name:COPY.en.analyze}));
 await screen.findByRole('heading',{name:COPY.en.result});
 expect(container.querySelector('.source-provenance time')?.getAttribute('datetime')).toBe('2026-10-23T04:00:00Z');
 vi.spyOn(navigator.clipboard,'writeText').mockImplementation(async(value)=>{clipboard=value});
 await user.click(screen.getByRole('button',{name:COPY.en.copy}));
 expect(clipboard).toContain('Retrieved: 2026-10-23T04:00:00Z');
 expect(container.querySelector('.print-evidence')?.textContent).toContain('Only students may apply.');
});
async function startText(){
 const user=userEvent.setup();render(<App/>);
 await user.click(screen.getByRole('button',{name:'English'}));
 await user.click(screen.getByRole('button',{name:COPY.en.text}));
 return user;
}
async function review(user:ReturnType<typeof userEvent.setup>){
 await user.type(screen.getByLabelText(COPY.en.paste),'Students pay no fee; others pay 100 taka.');
 await user.click(screen.getByRole('button',{name:'Review this text'}));
}
describe('Notice journey',()=>{
 it('replaces image drafts and preserves the selected image through actionable errors',async()=>{
 vi.stubGlobal('URL',Object.assign(class extends URL {},{createObjectURL:vi.fn(()=> 'blob:local-test'),revokeObjectURL:vi.fn()}));
 const user=userEvent.setup();render(<App/>);extract=true;
 await user.click(screen.getByRole('button',{name:'English'}));
 await user.click(screen.getByRole('button',{name:COPY.en.image}));
 await user.upload(screen.getByLabelText(COPY.en.imageLabel),new File(['first'],'first.png',{type:'image/png'}));
 await user.click(screen.getByRole('button',{name:'Read the image text'}));
 await screen.findByRole('heading',{name:'This is the text we will explain'});
 expect(screen.getByRole('link',{name:'Open full-size image'}).getAttribute('href')).toBe('blob:local-test');
 await user.click(screen.getByRole('button',{name:'Go back'}));
 expect(screen.getByRole('button',{name:'Review saved text'})).toBeTruthy();
 await user.upload(screen.getByLabelText(COPY.en.imageLabel),new File(['second'],'second.png',{type:'image/png'}));
 expect(screen.queryByRole('button',{name:'Review saved text'})).toBeNull();
 for(const [code,message] of [['image_size','The image exceeds 5 MB'],['image_invalid','We cannot read this image'],['image_dimensions','The image dimensions are too large'],['image_empty','No readable text was found']]){
 outcome=code;await user.click(screen.getByRole('button',{name:'Read the image text'}));
 await waitFor(()=>expect(screen.getByRole('alert').textContent).toContain(message));
 expect(screen.getByText('second.png')).toBeTruthy();
 expect(screen.getByRole('img',{name:COPY.en.imageLabel}).getAttribute('src')).toBe('blob:local-test');
 expect(screen.queryByRole('button',{name:COPY.en.analyze})).toBeNull();
 }
 const calls=vi.mocked(fetch).mock.calls.length;
 await user.upload(screen.getByLabelText(COPY.en.imageLabel),new File([new Uint8Array(5*1024*1024+1)],'oversized.png',{type:'image/png'}));
 expect(screen.getByRole('alert').textContent).toContain('The image exceeds 5 MB');
 expect(screen.getByRole('button',{name:'Read the image text'}).hasAttribute('disabled')).toBe(true);
 expect(screen.queryByRole('img',{name:COPY.en.imageLabel})).toBeNull();
 expect(vi.mocked(fetch).mock.calls.length).toBe(calls);
 });
 it('restores extracted draft provenance across input methods without another extraction',async()=>{
 const user=userEvent.setup();const {container}=render(<App/>);extract=true;
 await user.click(screen.getByRole('button',{name:'English'}));
 await user.click(screen.getByRole('button',{name:COPY.en.link}));await user.type(screen.getByLabelText('Public page URL'),'https://example.gov.bd/a');
 await user.click(screen.getByRole('button',{name:'Read the linked page'}));
 await screen.findByRole('heading',{name:'This is the text we will explain'});
 await user.type(screen.getByLabelText('Original text'),' Edited.');
 await user.click(screen.getByRole('checkbox'));
 const calls=vi.mocked(fetch).mock.calls.length;
 await user.click(screen.getByRole('button',{name:'Go back'}));
 await user.click(screen.getByRole('button',{name:'Read the linked page'}));
 expect(vi.mocked(fetch).mock.calls.length).toBe(calls);
 await user.click(screen.getByRole('button',{name:'Go back'}));
 await user.click(screen.getByRole('button',{name:COPY.en.text}));
 await user.type(screen.getByLabelText(COPY.en.paste),'Separate pasted draft');
 await user.click(screen.getByRole('button',{name:COPY.en.link}));
 await user.click(screen.getByRole('button',{name:'Review saved text'}));
 expect(vi.mocked(fetch).mock.calls.length).toBe(calls);
 expect((screen.getByLabelText('Original text') as HTMLTextAreaElement).value).toContain('Edited.');
 expect(screen.getByText('This text has been edited since extraction.')).toBeTruthy();
 expect((screen.getByRole('checkbox') as HTMLInputElement).checked).toBe(false);
 extract=false;
 await user.click(screen.getByRole('checkbox'));
 await user.click(screen.getByRole('button',{name:COPY.en.analyze}));
 await screen.findByRole('heading',{name:COPY.en.result});
 expect(container.querySelector('.source-provenance')?.textContent).toContain('https://example.gov.bd/b');
 expect(screen.getByText(/Retrieved:/)).toBeTruthy();
 await user.click(screen.getByRole('button',{name:COPY.en.edit}));
 await user.click(screen.getByRole('button',{name:'Go back'}));
 await user.clear(screen.getByLabelText('Public page URL'));
 await user.click(screen.getByRole('button',{name:COPY.en.link}));await user.type(screen.getByLabelText('Public page URL'),'https://example.gov.bd/replacement');
 expect(screen.queryByRole('button',{name:'Review saved text'})).toBeNull();
 await user.click(screen.getByRole('button',{name:COPY.en.text}));
 expect(screen.getByLabelText(COPY.en.paste)).toHaveProperty('value','Separate pasted draft');
 });
 it('moves focus to review and supports keyboard confirmation',async()=>{
 const user=await startText();await review(user);
 expect(document.activeElement).toBe(screen.getByRole('heading',{name:'This is the text we will explain'}));
 await user.tab();
 expect(document.activeElement).toBe(screen.getByLabelText('Original text'));
 await user.tab();
 expect(document.activeElement).toBe(screen.getByRole('checkbox'));
 await user.keyboard(' ');
 expect((screen.getByRole('checkbox') as HTMLInputElement).checked).toBe(true);
 expect((screen.getByRole('button',{name:COPY.en.analyze}) as HTMLButtonElement).disabled).toBe(false);
 });

 it('restores the original draft after exploring the saved example',async()=>{
 const user=await startText();
 await user.type(screen.getByLabelText(COPY.en.paste),'My original public notice');
 await user.click(screen.getByRole('button',{name:/Explore an example first/}));await finishWalkthrough(user);
 await screen.findByRole('heading',{name:COPY.en.result});
 expect(screen.getByText(/Fictional example · prepared in advance/)).toBeTruthy();
 await user.click(screen.getAllByRole('button',{name:JOURNEY_COPY.en.exit})[0]);
 expect((screen.getByLabelText(COPY.en.paste) as HTMLTextAreaElement).value).toBe('My original public notice');
 });

 it('reuses unchanged results through Back/Next and invalidates edited sources',async()=>{
 const user=await startText();await review(user);await user.click(screen.getByRole('checkbox'));
 await user.click(screen.getByRole('button',{name:COPY.en.analyze}));await screen.findByRole('heading',{name:COPY.en.result});
 const submissions=()=>vi.mocked(fetch).mock.calls.filter(([url])=>String(url).endsWith('/api/analysis')).length;
 expect(submissions()).toBe(1);
 await user.click(screen.getByRole('button',{name:COPY.en.edit}));await user.click(screen.getByRole('button',{name:'Go back'}));
 await user.click(screen.getByRole('button',{name:/Explore an example first/}));
 await user.click(screen.getByRole('button',{name:'Next step'}));
 await user.click(screen.getByRole('button',{name:JOURNEY_COPY.en.exit}));
 await user.click(screen.getByRole('button',{name:'Review this text'}));expect(screen.getByRole('checkbox')).toHaveProperty('checked',true);
 await user.click(screen.getByRole('button',{name:'Next step'}));expect(submissions()).toBe(1);
 await user.click(screen.getByRole('button',{name:COPY.en.edit}));
 fireEvent.change(screen.getByLabelText('Original text'),{target:{value:'Changed public notice'}});
 expect(screen.getByRole('checkbox')).toHaveProperty('checked',false);expect(screen.queryByRole('button',{name:'Next step'})).toBeNull();
 await user.click(screen.getByRole('checkbox'));await user.click(screen.getByRole('button',{name:COPY.en.analyze}));
 await screen.findByRole('heading',{name:COPY.en.result});expect(submissions()).toBe(2);
 });

 it('labels a result with no safe guidance explicitly',async()=>{
 const user=await startText();await review(user);outcome='noguidance';
 await user.click(screen.getByRole('checkbox'));
 await user.click(screen.getByRole('button',{name:COPY.en.analyze}));
 await screen.findByRole('heading',{name:'We could not establish safe next steps'});
 expect(screen.queryByRole('heading',{name:COPY.en.result})).toBeNull();
 expect(screen.getByText(/did not support guidance/)).toBeTruthy();
 vi.spyOn(navigator.clipboard,'writeText').mockImplementation(async(value)=>{clipboard=value});
 await user.click(screen.getByRole('button',{name:COPY.en.copy}));
 expect(clipboard.startsWith(COPY.en.brand+'\n\n'+COPY.en.noGuidance)).toBe(true);
 expect(clipboard).toContain('This text did not support guidance we could safely show.');
 });

 it.each(['https://example.gov.bd/b',''])('retains differing or unknown destination in result and copy: %s',async(destination)=>{
 const user=userEvent.setup();const {container}=render(<App/>);extract=true;reportedUrl=destination;
 await user.click(screen.getByRole('button',{name:'English'}));
 await user.click(screen.getByRole('button',{name:COPY.en.link}));await user.type(screen.getByLabelText('Public page URL'),'https://example.gov.bd/a');
 await user.click(screen.getByRole('button',{name:'Read the linked page'}));
 await screen.findByRole('heading',{name:'This is the text we will explain'});
 await user.type(screen.getByLabelText('Original text'),' Edited.');
 extract=false;
 await user.click(screen.getByRole('checkbox'));
 await user.click(screen.getByRole('button',{name:COPY.en.analyze}));
 await screen.findByRole('heading',{name:COPY.en.result});
 const provenance=container.querySelector('.source-provenance')!;
 expect(provenance.textContent).toContain('Requested URL: https://example.gov.bd/a');
 expect(provenance.textContent).toContain('Reported URL: '+(destination||'Unknown—check the original source.'));
 expect(screen.getByText('This text has been edited since extraction.')).toBeTruthy();
 expect(screen.getByText(/Retrieved:/)).toBeTruthy();
 vi.spyOn(navigator.clipboard,'writeText').mockImplementation(async(value)=>{clipboard=value});
 await user.click(screen.getByRole('button',{name:COPY.en.copy}));
 expect(clipboard).toContain(provenance.textContent!.includes('Unknown')?'Reported URL: Unknown—check the original source.':'Reported URL: '+destination);
 expect(clipboard).toContain('Requested URL: https://example.gov.bd/a');
 expect(clipboard).toContain('Text edited after extraction.');
 expect(clipboard).toContain('2026-10-23T04:00:00Z');
 });

 it('preserves the text draft across input changes',async()=>{
 const user=await startText();
 await user.type(screen.getByLabelText(COPY.en.paste),'Keep this draft');
 await user.click(screen.getByRole('button',{name:COPY.en.link}));
 await user.click(screen.getByRole('button',{name:COPY.en.text}));
 expect((screen.getByLabelText(COPY.en.paste) as HTMLTextAreaElement).value).toBe('Keep this draft');
 });
 it('requires confirmation and resets it after edits',async()=>{
 const user=await startText();await review(user);
 const action=screen.getByRole('button',{name:COPY.en.analyze}) as HTMLButtonElement;
 expect(action.disabled).toBe(true);
 await user.click(screen.getByRole('checkbox'));
 expect(action.disabled).toBe(false);
 await user.type(screen.getByLabelText('Original text'),' Edited.');
 expect((screen.getByRole('checkbox') as HTMLInputElement).checked).toBe(false);
 expect(action.disabled).toBe(true);
 });
 it.each(['failed','capacity','review-failed','malformed-analysis'])('preserves reviewed source after %s',async(failure)=>{
 const user=await startText();await review(user);outcome=failure;
 await user.click(screen.getByRole('checkbox'));
 await user.click(screen.getByRole('button',{name:COPY.en.analyze}));
 await screen.findByRole('alert');
 expect(document.activeElement).toBe(screen.getByRole('alert'));
 expect((screen.getByLabelText('Original text') as HTMLTextAreaElement).value).toContain('Students pay no fee');
 expect((screen.getByRole('checkbox') as HTMLInputElement).checked).toBe(true);
 expect(screen.queryByRole('heading',{name:COPY.en.result})).toBeNull();
 if(failure==='malformed-analysis')expect(screen.getByRole('alert').textContent).not.toContain('this page');
 if(failure==='review-failed')expect(screen.getByRole('alert').textContent).toContain('no explanation was shown');
 });
 it('gives actionable page-extraction failures without starting analysis',async()=>{
 const user=userEvent.setup();render(<App/>);await user.click(screen.getByRole('button',{name:'English'}));
 await user.click(screen.getByRole('button',{name:COPY.en.link}));await user.type(screen.getByLabelText('Public page URL'),'https://example.gov.bd/public');
 for(const code of ['access_denied','incomplete_content','empty_content','malformed_response','text_too_long','response_too_large']){
 outcome='link-error:'+code;await user.click(screen.getByRole('button',{name:'Read the linked page'}));
 await waitFor(()=>expect(screen.getByRole('alert').textContent).toContain(code==='access_denied'?'cannot access this page':'complete, readable text'));
 expect(screen.getByLabelText('Public page URL')).toHaveProperty('value','https://example.gov.bd/public');
 }
 expect(vi.mocked(fetch).mock.calls.some(([path])=>String(path)==='/api/analysis')).toBe(false);
 });
 it('shows retrieved destination differences and edited-source status',async()=>{
 const user=userEvent.setup();render(<App/>);extract=true;
 await user.click(screen.getByRole('button',{name:'English'}));
 await user.click(screen.getByRole('button',{name:COPY.en.link}));await user.type(screen.getByLabelText('Public page URL'),'https://example.gov.bd/a');
 await user.click(screen.getByRole('button',{name:'Read the linked page'}));
 await screen.findByRole('heading',{name:'This is the text we will explain'});
 expect(screen.getByText(/reported destination differs/)).toBeTruthy();
 await user.type(screen.getByLabelText('Original text'),' Edited.');
 expect(screen.getByText('This text has been edited since extraction.')).toBeTruthy();
 });
 it('keeps the existing example language after changing interface language',async()=>{
 const user=userEvent.setup();render(<App/>);
 await user.click(screen.getByRole('button',{name:'English'}));
 await user.click(screen.getByRole('button',{name:/Explore an example first/}));await finishWalkthrough(user);
 await screen.findByRole('heading',{name:COPY.en.result});
 await user.click(screen.getByRole('button',{name:'বাংলা'}));
 expect(screen.getByText(/ব্যাখ্যার ভাষা:/).textContent).toContain('English');
 expect(screen.getAllByText(example.result.sections.explanation[0].text).length).toBeGreaterThan(0);
 expect(vi.mocked(fetch).mock.calls.every(([path])=>(String(path).includes('examples.json')||String(path).endsWith('/api/health')))).toBe(true);
 });
 it('looks up a lost submission response using its request ID without another analysis POST',async()=>{
 const user=await startText();await review(user);await user.click(screen.getByRole('checkbox'));
 outcome='lost-submission';await user.click(screen.getByRole('button',{name:COPY.en.analyze}));
 await screen.findByRole('button',{name:'Check the existing request'});
 const submission=vi.mocked(fetch).mock.calls.find(([path])=>String(path)==='/api/analysis')!;
 const requestId=JSON.parse((submission[1] as RequestInit).body as string).request_id;
 expect(requestId).toBeTruthy();
 outcome='success';await user.click(screen.getByRole('button',{name:'Check the existing request'}));
 await screen.findByRole('heading',{name:COPY.en.result});
 expect(vi.mocked(fetch).mock.calls.filter(([path])=>String(path)==='/api/analysis')).toHaveLength(1);
 expect(vi.mocked(fetch).mock.calls.some(([path])=>String(path)==='/api/requests/'+requestId)).toBe(true);
 });
 it('resumes status polling without sending a second analysis and preserves drafts when jobs expire',async()=>{
 const user=await startText();await review(user);await user.click(screen.getByRole('checkbox'));
 outcome='disconnected';await user.click(screen.getByRole('button',{name:COPY.en.analyze}));
 await screen.findByRole('button',{name:'Check the existing request'});
 expect(screen.getByRole('button',{name:COPY.en.analyze}).hasAttribute('disabled')).toBe(true);
 expect(screen.getByRole('textbox',{name:'Original text'})).toHaveProperty('value','Students pay no fee; others pay 100 taka.');
 const submissions=()=>vi.mocked(fetch).mock.calls.filter(([path])=>String(path)==='/api/analysis').length;
 expect(submissions()).toBe(1);
 outcome='success';await user.click(screen.getByRole('button',{name:'Check the existing request'}));
 await screen.findByRole('heading',{name:COPY.en.result});expect(submissions()).toBe(1);
 await user.click(screen.getByRole('button',{name:COPY.en.edit}));fireEvent.change(screen.getByRole('textbox',{name:'Original text'}),{target:{value:'Students pay no fee; others pay 100 taka. '}});await user.click(screen.getByRole('checkbox'));
 outcome='disconnected';await user.click(screen.getByRole('button',{name:COPY.en.analyze}));
 await screen.findByRole('button',{name:'Check the existing request'});
 outcome='expired';await user.click(screen.getByRole('button',{name:'Check the existing request'}));
 await waitFor(()=>expect(screen.getByRole('alert').textContent).toContain('no longer available'));
 expect(screen.queryByRole('button',{name:'Check the existing request'})).toBeNull();
 expect(screen.getByRole('textbox',{name:'Original text'})).toHaveProperty('value','Students pay no fee; others pay 100 taka. ');
 expect(submissions()).toBe(2);
 });
 it('recovers interrupted link extraction into review without extracting again or starting analysis',async()=>{
 const user=userEvent.setup();render(<App/>);extract=true;
 await user.click(screen.getByRole('button',{name:'English'}));
 await user.click(screen.getByRole('button',{name:COPY.en.link}));await user.type(screen.getByLabelText('Public page URL'),'https://example.gov.bd/a');
 outcome='disconnected';await user.click(screen.getByRole('button',{name:'Read the linked page'}));
 await screen.findByRole('button',{name:'Check the existing request'});
 outcome='success';await user.click(screen.getByRole('button',{name:'Check the existing request'}));
 await screen.findByRole('heading',{name:'This is the text we will explain'});
 expect(screen.getByRole('textbox',{name:'Original text'})).toHaveProperty('value','Only students may apply. Fee 100 taka.');
 expect(screen.getByRole('button',{name:COPY.en.analyze}).hasAttribute('disabled')).toBe(true);
 const paths=vi.mocked(fetch).mock.calls.map(([path])=>String(path));
 expect(paths.filter(path=>path==='/api/extract/link')).toHaveLength(1);
 expect(paths.filter(path=>path==='/api/analysis')).toHaveLength(0);
 expect(screen.getByRole('link',{name:COPY.en.original}).getAttribute('href')).toBe('https://example.gov.bd/a');
 });
 it('discards interrupted request recovery when its source is edited',async()=>{
 const user=await startText();await review(user);await user.click(screen.getByRole('checkbox'));
 outcome='disconnected';await user.click(screen.getByRole('button',{name:COPY.en.analyze}));
 await screen.findByRole('button',{name:'Check the existing request'});
 await user.type(screen.getByRole('textbox',{name:'Original text'}),' Changed.');
 expect(screen.queryByRole('button',{name:'Check the existing request'})).toBeNull();
 expect(screen.getByRole('button',{name:COPY.en.analyze}).hasAttribute('disabled')).toBe(true);
 expect(screen.queryByRole('heading',{name:COPY.en.result})).toBeNull();
 });
 it('keeps missing, conflicting and unverified points distinct in UI and copied output',async()=>{
 outcome='uncertainties';const user=await startText();await review(user);
 await user.click(screen.getByRole('checkbox'));await user.click(screen.getByRole('button',{name:COPY.en.analyze}));
 await screen.findByRole('heading',{name:COPY.en.result});
 for(const label of ['Information needed to proceed','Conflicting information','Information we could not confirm'])expect(screen.getByText(label)).toBeTruthy();
 vi.spyOn(navigator.clipboard,'writeText').mockImplementation(async(value)=>{clipboard=value});
 await user.click(screen.getByRole('button',{name:COPY.en.copy}));
 await waitFor(()=>expect(clipboard).toContain('Other information: The two dates differ. [e1, e4]'));
 expect(clipboard).toContain('Information needed to proceed');
 expect(clipboard).toContain('Other information: The passage gives no fee.');
 expect(clipboard).toContain('Other information: Applicability could not be established.');
 await user.click(screen.getByRole('button',{name:'বাংলা'}));
 for(const label of ['এগিয়ে যেতে যে তথ্যগুলো জানা প্রয়োজন','তথ্যে বিরোধ বা অসামঞ্জস্য','যে তথ্যগুলো নিশ্চিত করা যায়নি'])expect(screen.getByText(label)).toBeTruthy();
 });
 it('keeps the full copy export and removes the visible preview',async()=>{
 const user=userEvent.setup();const {container}=render(<App/>);
 await user.click(screen.getByRole('button',{name:'English'}));
 await openMockResult(user);
 await screen.findByRole('heading',{name:COPY.en.result});
 vi.spyOn(navigator.clipboard,'writeText').mockImplementation(async(value)=>{clipboard=value});
 await user.click(screen.getByRole('button',{name:COPY.en.copy}));
 expect(container.querySelector('.copy-preview')).toBeNull();expect(container.querySelector('.copy-box')?.contains(screen.getByRole('button',{name:COPY.en.copied}))).toBe(true);
 expect(clipboard).toContain(COPY.en.result);
 expect(clipboard).toContain(example.source);
 expect(clipboard).toContain(example.result.evidence[0].excerpt);
 for(const claims of Object.values(example.result.sections))for(const claim of claims)expect(clipboard).toContain(claim.text+' ['+claim.evidence_ids.join(', ')+']');
 expect(clipboard).toContain('not a complete service guide');
 });
 it('offers the complete summary for manual copying when clipboard access fails',async()=>{
 const user=userEvent.setup();render(<App/>);
 await user.click(screen.getByRole('button',{name:'English'}));
 await openMockResult(user);
 await screen.findByRole('heading',{name:COPY.en.result});
 vi.spyOn(navigator.clipboard,'writeText').mockRejectedValue(new DOMException('Denied','NotAllowedError'));
 await user.click(screen.getByRole('button',{name:COPY.en.copy}));
 const fallback=await screen.findByRole('textbox',{name:'Select and copy the summary'}) as HTMLTextAreaElement;
 expect(fallback.value).toContain(example.source);expect(fallback.value).toContain(COPY.en.result);
 expect(fallback.value).toContain(example.result.sections.fees[0].text+' ['+example.result.sections.fees[0].evidence_ids.join(', ')+']');
 expect(fallback.value).toContain('not a complete service guide');
 expect(document.activeElement).toBe(fallback);expect(fallback.selectionEnd).toBe(fallback.value.length);
 await user.click(screen.getByRole('button',{name:COPY.en.edit}));
 expect(screen.queryByRole('textbox',{name:'Select and copy the summary'})).toBeNull();
 });
 it('includes all evidence in a dedicated print section',async()=>{
 const user=userEvent.setup();const {container}=render(<App/>);
 await user.click(screen.getByRole('button',{name:'English'}));
 await openMockResult(user);
 await screen.findByRole('heading',{name:COPY.en.result});
 const print=vi.spyOn(window,'print').mockImplementation(()=>{});
 await user.click(screen.getByRole('button',{name:'Print'}));
 expect(print).toHaveBeenCalledOnce();
 const printable=container.querySelector('.print-evidence')!;
 expect(printable.textContent).toContain(example.source);
 for(const item of example.result.evidence)expect(printable.textContent).toContain('['+item.id+'] '+item.excerpt);
 for(const claims of Object.values(example.result.sections))for(const claim of claims){
 const displayed=Array.from(container.querySelectorAll('.claim p')).find(p=>p.textContent?.startsWith(claim.text));
 expect(displayed?.querySelector('.print-reference')?.textContent).toBe(' ['+claim.evidence_ids.join(', ')+']');
 }
 expect(printable.textContent).toContain('AI can make mistakes');
 });
});

// Migrated from the former Streamlit image workflow: actual React controls.
it('keeps corrected image text across language and method changes and requires renewed review',async()=>{
 const user=userEvent.setup();render(<App/>);extract=true;
 vi.spyOn(URL,'createObjectURL').mockReturnValue('blob:image-workflow');
 vi.spyOn(URL,'revokeObjectURL').mockImplementation(()=>{});
 await user.click(screen.getByRole('button',{name:'English'}));
 await user.click(screen.getByRole('button',{name:COPY.en.image}));
 expect(screen.getByText(/The image will be sent to Google Gemini/)).toBeTruthy();
 await user.upload(screen.getByLabelText(COPY.en.imageLabel),new File(['image'],'notice.png',{type:'image/png'}));
 await user.click(screen.getByRole('button',{name:'Read the image text'}));
 await screen.findByRole('heading',{name:'This is the text we will explain'});
 await user.click(screen.getByRole('checkbox'));
 await user.type(screen.getByLabelText('Original text'),' Corrected.');
 expect((screen.getByRole('checkbox') as HTMLInputElement).checked).toBe(false);
 expect(screen.getByRole('button',{name:COPY.en.analyze}).hasAttribute('disabled')).toBe(true);
 const calls=vi.mocked(fetch).mock.calls.length;
 await user.click(screen.getByRole('button',{name:'বাংলা'}));
 await user.click(screen.getByRole('button',{name:'English'}));
 expect((screen.getByLabelText('Original text') as HTMLTextAreaElement).value).toContain('Corrected.');
 await user.click(screen.getByRole('button',{name:'Go back'}));
 await user.click(screen.getByRole('button',{name:COPY.en.text}));
 await user.type(screen.getByLabelText(COPY.en.paste),'Separate draft');
 await user.click(screen.getByRole('button',{name:COPY.en.image}));
 expect(screen.getByText('notice.png')).toBeTruthy();
 await user.click(screen.getByRole('button',{name:'Review saved text'}));
 expect((screen.getByLabelText('Original text') as HTMLTextAreaElement).value).toContain('Corrected.');
 expect((screen.getByRole('checkbox') as HTMLInputElement).checked).toBe(false);
 expect(vi.mocked(fetch).mock.calls.length).toBe(calls);
});

it('locks image and language controls while OCR is pending without duplicate submission',async()=>{
 const user=userEvent.setup();render(<App/>);extract=true;
 vi.spyOn(URL,'createObjectURL').mockReturnValue('blob:busy-image');
 vi.spyOn(URL,'revokeObjectURL').mockImplementation(()=>{});
 await user.click(screen.getByRole('button',{name:'English'}));
 await user.click(screen.getByRole('button',{name:COPY.en.image}));
 await user.upload(screen.getByLabelText(COPY.en.imageLabel),new File(['image'],'notice.png',{type:'image/png'}));
 const original=fetch;let release!:()=>void;
 const pending=new Promise<void>(resolve=>{release=resolve});
 const transport=vi.fn(async(input:RequestInfo|URL,options?:RequestInit)=>{
  if(String(input).includes('/api/extract/image'))await pending;
  return original(input,options);
 });vi.stubGlobal('fetch',transport);
 await user.click(screen.getByRole('button',{name:'Read the image text'}));
 await waitFor(()=>expect(transport.mock.calls.some(c=>String(c[0]).includes('/api/extract/image'))).toBe(true));
 try{
  expect(screen.getByRole('button',{name:'English'}).hasAttribute('disabled')).toBe(true);
  expect(screen.queryByRole('button',{name:COPY.en.text})).toBeNull();
  expect(screen.queryByLabelText(COPY.en.imageLabel)).toBeNull();
  await user.click(screen.getByRole('button',{name:'English'}));
  expect(transport.mock.calls.filter(c=>String(c[0]).includes('/api/extract/image'))).toHaveLength(1);
 }finally{release()}
 await screen.findByRole('heading',{name:'This is the text we will explain'});
 expect(screen.getByRole('button',{name:'English'}).hasAttribute('disabled')).toBe(false);
});

async function finishWalkthrough(user:{click:(element:HTMLElement)=>Promise<unknown>}){
 await user.click(screen.getByRole('button',{name:/^Next step$|^পরের ধাপে$/}));
 await user.click(screen.getByRole('button',{name:/^Next step$|^পরের ধাপে$/}));
}

async function openMockResult(user:{click:(element:HTMLElement)=>Promise<unknown>}){
 await user.click(screen.getByRole('button',{name:COPY.en.text}));
 fireEvent.change(screen.getByLabelText(COPY.en.paste),{target:{value:examples['en-general'].source}});
 await user.click(screen.getByRole('button',{name:'Review this text'}));
 await user.click(screen.getByRole('checkbox'));
 await user.click(screen.getByRole('button',{name:COPY.en.analyze}));
 await screen.findByRole('heading',{name:COPY.en.result});
}

it('uses identical empty states and uncertainty groups on screen, copy and print',async()=>{
 outcome='section-states';const user=await startText();await review(user);
 await user.click(screen.getByRole('checkbox'));await user.click(screen.getByRole('button',{name:COPY.en.analyze}));
 await screen.findByRole('heading',{name:COPY.en.result});
 expect(screen.getByText('Not stated in the source.')).toBeTruthy();
 expect(screen.getByText('We could not confirm this section. See what remains unclear below.')).toBeTruthy();
 expect(screen.getByText('Some information in this section could not be confirmed. Read the limitations below.')).toBeTruthy();
 vi.spyOn(navigator.clipboard,'writeText').mockImplementation(async(value)=>{clipboard=value});
 await user.click(screen.getByRole('button',{name:COPY.en.copy}));
 for(const text of ['Not stated in the source.','We could not confirm this section.','Information needed to proceed','Information we could not confirm','Document conditions remain unclear.'])expect(clipboard).toContain(text);
 expect(clipboard.indexOf('Information needed to proceed')).toBeLessThan(clipboard.indexOf('Information we could not confirm'));
 expect(document.querySelector('.unknowns .uncertainty-group h4')?.textContent).toBe('Information needed to proceed');
 expect(document.querySelector('.print-evidence')?.textContent).toContain('e1');
});

it('keeps alpha input disabled while the complete saved journey works without network calls',async()=>{
 vi.stubEnv('MODE','alpha');const user=userEvent.setup();render(<App initialLanguage="en"/>);
 await user.click(screen.getByRole('button',{name:COPY.en.link}));
 expect(screen.getByRole('button',{name:COPY.en.linkButton}).hasAttribute('disabled')).toBe(true);
 await user.click(screen.getByRole('button',{name:new RegExp(COPY.en.example)}));
 await user.click(screen.getByRole('button',{name:JOURNEY_COPY.en.next}));
 await screen.findByRole('heading',{name:COPY.en.reviewTitle});
 await user.click(screen.getByRole('button',{name:JOURNEY_COPY.en.next}));
 await screen.findByRole('heading',{name:COPY.en.result});
 expect(vi.mocked(fetch)).not.toHaveBeenCalled();
});

it('shows attached source conditions on the item and retains them in copy and print DOM',async()=>{
 outcome='attached-context';const user=await startText();await review(user);
 await user.click(screen.getByRole('checkbox'));await user.click(screen.getByRole('button',{name:COPY.en.analyze}));
 await screen.findByRole('heading',{name:COPY.en.result});
 const context=document.querySelector('.source-conditions');
 expect(context?.textContent).toContain('Only current students who live in this district may apply.');
 const checkbox=screen.getByRole('checkbox',{name:/^Submit the form\./});
 expect(checkbox.getAttribute('aria-describedby')).toBe(context?.id);
 vi.spyOn(navigator.clipboard,'writeText').mockImplementation(async(value)=>{clipboard=value});
 await user.click(screen.getByRole('button',{name:COPY.en.copy}));
 expect(clipboard).toContain('Submit the form. [e1]\nConditions for this item · original source wording\n“Only current students who live in this district may apply.”');
});

it('enables real analysis in the labelled live alpha and keeps conditions in the result',async()=>{
 vi.stubEnv('MODE','live-alpha');outcome='attached-context';const user=await startText();
 expect(screen.getByText(/Experimental version · You can analyze a new notice/)).toBeTruthy();
 await review(user);await user.click(screen.getByRole('checkbox'));await user.click(screen.getByRole('button',{name:COPY.en.analyze}));
 await screen.findByRole('heading',{name:COPY.en.result});
 expect(vi.mocked(fetch).mock.calls.some(([path])=>String(path).endsWith('/api/analysis'))).toBe(true);
 expect(document.querySelector('.source-conditions')?.textContent).toContain('Only current students');
});
