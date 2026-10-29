import {COPY} from './uiCopy';
import {webcrypto} from 'node:crypto';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {act,cleanup,render,renderHook,screen,waitFor,fireEvent} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {App} from '../legacy/LegacyJourney';
import {createApiClient,streamJob} from './api';
import {useServerHealth} from '../legacy/useServerHealth';
import examples from '../public/examples.json';
beforeEach(()=>{
 localStorage.clear();
 vi.stubGlobal('crypto',{randomUUID:()=>webcrypto.randomUUID(),subtle:webcrypto.subtle});
 vi.stubGlobal('fetch',vi.fn(async(input:unknown)=>{
  const path=String(input);
  if(path.includes('examples.json'))return new Response(JSON.stringify(examples));
  if(path.endsWith('/api/health'))return new Response(JSON.stringify({status:'ok'}));
  if(path.endsWith('/api/session'))return new Response(JSON.stringify({token:'fresh-token'}));
  if(path.includes('/api/jobs/'))return new Response(JSON.stringify({status:'succeeded',stage:'done',result:{...examples['en-general'].result,review_mode:'deterministic_only',semantic_review_complete:false,demo:false}}));
  return new Response(JSON.stringify({job_id:'job'}),{status:202});
 }));
});
afterEach(()=>{cleanup();vi.useRealTimers();vi.restoreAllMocks();vi.unstubAllGlobals();localStorage.clear()});
it('offers one synthetic walkthrough and reaches prepared guidance without an API request',async()=>{
 const user=userEvent.setup();render(<App/>);await user.click(screen.getByRole('button',{name:'English'}));
 expect(screen.queryByRole('button',{name:/saved e-passport/})).toBeNull();
 await user.click(screen.getByRole('button',{name:/Explore an example first/}));
 expect(screen.getByText(/Fictional example · prepared in advance/)).toBeTruthy();
 await finishWalkthrough(user);
 await screen.findByText('Fictional example');
 expect(vi.mocked(fetch).mock.calls.every(([path])=>String(path).endsWith('/api/health'))).toBe(true);
});
it('restores checklist flags for the same result, resets them and exports completion marks',async()=>{
 const user=userEvent.setup();const first=render(<App/>);
 await user.click(screen.getByRole('button',{name:'English'}));await openMockResult(user);
 const action=await screen.findByRole('checkbox',{name:/Complete and submit/});
 await waitFor(()=>expect(action.hasAttribute('disabled')).toBe(false));await user.click(action);
 const key=Object.keys(localStorage).find(k=>k.startsWith('shobuj-checklist-v1:'))!;
 expect(JSON.parse(localStorage.getItem(key)!).checked).toContain('steps:0');
 expect(localStorage.getItem(key)).not.toContain(examples['en-general'].source);
 const write=vi.spyOn(navigator.clipboard,'writeText').mockResolvedValue();
 await user.click(screen.getByRole('button',{name:COPY.en.copy}));
 expect(write.mock.calls[0][0]).toContain('[✓] '+examples['en-general'].result.sections.steps[0].text+' ['+examples['en-general'].result.sections.steps[0].evidence_ids.join(', ')+']');
 expect(action.closest('label')?.getAttribute('data-print-marker')).toBe('[✓]');
 first.unmount();render(<App/>);await user.click(screen.getByRole('button',{name:'English'}));
 await openMockResult(user);
 const restored=await screen.findByRole('checkbox',{name:/Complete and submit/});
 await waitFor(()=>expect((restored as HTMLInputElement).checked).toBe(true));
 await user.click(screen.getByRole('button',{name:'Reset checklist'}));
 expect((restored as HTMLInputElement).checked).toBe(false);
 expect(JSON.parse(localStorage.getItem(key)!).checked).toEqual([]);
});
it('labels deterministic-only guidance in the result and copied summary',async()=>{
 const user=userEvent.setup();render(<App/>);await user.click(screen.getByRole('button',{name:'English'}));
 await user.click(screen.getByRole('button',{name:COPY.en.text}));await user.type(screen.getByLabelText(COPY.en.paste),'Public example source.');
 await user.click(screen.getByRole('button',{name:'Review this text'}));await user.click(screen.getByRole('checkbox'));
 await user.click(screen.getByRole('button',{name:COPY.en.analyze}));
 await screen.findByText(/AI review did not complete/);
 const write=vi.spyOn(navigator.clipboard,'writeText').mockResolvedValue();await user.click(screen.getByRole('button',{name:COPY.en.copy}));
 expect(write.mock.calls[0][0]).toContain('meaning and complete conditions remain unverified');
});
it('keeps manual-copy fallback current after checklist and interface changes',async()=>{
 const user=userEvent.setup();render(<App/>);
 await user.click(screen.getByRole('button',{name:'English'}));
 await openMockResult(user);
 const action=await screen.findByRole('checkbox',{name:/Complete and submit/});
 await waitFor(()=>expect(action.hasAttribute('disabled')).toBe(false));
 vi.spyOn(navigator.clipboard,'writeText').mockRejectedValue(new DOMException('Denied','NotAllowedError'));
 await user.click(screen.getByRole('button',{name:COPY.en.copy}));
 const fallback=await screen.findByRole('textbox',{name:'Select and copy the summary'});
 expect((fallback as HTMLTextAreaElement).value).toContain('[ ] '+examples['en-general'].result.sections.steps[0].text+' ['+examples['en-general'].result.sections.steps[0].evidence_ids.join(', ')+']');
 await user.click(action);
 expect((fallback as HTMLTextAreaElement).value).toContain('[✓] '+examples['en-general'].result.sections.steps[0].text+' ['+examples['en-general'].result.sections.steps[0].evidence_ids.join(', ')+']');
 await user.click(screen.getByRole('button',{name:'Reset checklist'}));
 expect((fallback as HTMLTextAreaElement).value).toContain('[ ] '+examples['en-general'].result.sections.steps[0].text+' ['+examples['en-general'].result.sections.steps[0].evidence_ids.join(', ')+']');
 await user.click(screen.getByRole('button',{name:'বাংলা'}));
 expect((fallback as HTMLTextAreaElement).value).toContain('ব্যাখ্যার ভাষা: English');
 expect((fallback as HTMLTextAreaElement).value).toContain(examples['en-general'].source);
});
it.each([401,403])('refreshes a rejected session once on %s and retains the request ID',async(status)=>{
 const calls:{url:string;options:RequestInit}[]=[];
 vi.stubGlobal('fetch',vi.fn(async(url:string,options:RequestInit)=>{
  calls.push({url,options});
  if(url.endsWith('/api/session'))return new Response(JSON.stringify({token:'new-token'}));
  return calls.filter(c=>c.url.endsWith('/api/analysis')).length===1?new Response(JSON.stringify({detail:'session_expired'}),{status}):new Response(JSON.stringify({job_id:'existing'}));
 }));
 const session={current:'old-token'},client=createApiClient('',session);
 const body=JSON.stringify({request_id:'same-id'});
 await expect(client.request('/api/analysis',{method:'POST',body})).resolves.toEqual({job_id:'existing'});
 expect(calls.map(c=>c.url)).toEqual(['/api/analysis','/api/session','/api/analysis']);
 expect(calls[0].options.body).toBe(calls[2].options.body);expect(session.current).toBe('new-token');
 expect((calls[2].options.headers as Record<string,string>)['X-Session-Token']).toBe('new-token');
});
it('stops after one session retry instead of looping',async()=>{
 const transport=vi.fn(async(url:string)=>url.endsWith('/api/session')?new Response(JSON.stringify({token:'new'})):new Response(JSON.stringify({detail:'session_expired'}),{status:401}));
 vi.stubGlobal('fetch',transport);await expect(createApiClient('',{current:'old'}).request('/api/jobs/missing')).rejects.toThrow('session_expired');
 expect(transport).toHaveBeenCalledTimes(3);
});
it('shows the delayed health pill and wakes again only after a long hidden interval',async()=>{
 vi.useFakeTimers();const now=Date.now();vi.setSystemTime(now);
 let complete!:()=>void;const ping=vi.fn(()=>new Promise<void>(resolve=>{complete=resolve}));
 const {result}=renderHook(()=>useServerHealth(ping));expect(ping).toHaveBeenCalledTimes(1);
 await act(async()=>{await vi.advanceTimersByTimeAsync(1999)});expect(result.current.state).toBe('idle');
 await act(async()=>{await vi.advanceTimersByTimeAsync(1)});expect(result.current.state).toBe('waking');
 await act(async()=>{complete();await Promise.resolve()});expect(result.current.state).toBe('idle');
 act(()=>{Object.defineProperty(document,'visibilityState',{configurable:true,value:'hidden'});document.dispatchEvent(new Event('visibilitychange'))});
 await act(async()=>{await vi.advanceTimersByTimeAsync(600001)});
 act(()=>{Object.defineProperty(document,'visibilityState',{configurable:true,value:'visible'});document.dispatchEvent(new Event('visibilitychange'))});
 expect(ping).toHaveBeenCalledTimes(2);await act(async()=>{complete();await Promise.resolve()});
});
it('parses fragmented SSE stages and returns the completed JSON result',async()=>{
 const encoder=new TextEncoder();const frames=['event: job\r\ndata: {"status":"running","stage":"verifying"}\r','\n\r\ndata: {"status":"succeeded","stage":"completed","result":{"ok":true}}\n\n'];
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(new ReadableStream({start(controller){for(const frame of frames)controller.enqueue(encoder.encode(frame));controller.close()}}),{headers:{'content-type':'text/event-stream'}})));
 const stages:string[]=[];const event=await streamJob('/api/jobs/id/stream','token',stage=>stages.push(stage));
 expect(stages).toEqual(['verifying','completed']);expect(event.result).toEqual({ok:true});
});

it('names Google Gemini before image submission in both languages',async()=>{
 const user=userEvent.setup();render(<App/>);
 await user.click(screen.getByRole('button',{name:COPY.bn.image}));
 expect(screen.getByText(/ছবিটি Google Gemini/)).toBeTruthy();
 await user.click(screen.getByRole('button',{name:'English'}));
 expect(screen.getByText(/image will be sent to Google Gemini/)).toBeTruthy();
});
it('explicitly warns about incomplete AI meaning review in Bangla',async()=>{
 const user=userEvent.setup();render(<App/>);
 await user.click(screen.getByRole('button',{name:COPY.bn.text}));
 await user.type(screen.getByLabelText(COPY.bn.paste),'Public example source.');
 await user.click(screen.getByRole('button',{name:'লেখা দেখে এগিয়ে যান'}));
 await user.click(screen.getByRole('checkbox'));
 await user.click(screen.getByRole('button',{name:COPY.bn.analyze}));
 await screen.findByText(/AI দিয়ে অর্থ ও শর্তের পর্যালোচনা শেষ হয়নি/);
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
