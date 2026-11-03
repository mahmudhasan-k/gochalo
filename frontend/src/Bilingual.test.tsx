import {afterEach,beforeEach,it,expect,vi} from 'vitest';
import {render,screen,cleanup,waitFor,fireEvent} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {COPY,ASK_COPY} from './uiCopy';
import {App} from '../legacy/LegacyJourney';
import examples from '../public/examples.json';

const excerpt='শর্ত:  “A & B” <script>alert(1)</script>।\n  ৫০০ টাকা; নয়!';
const baseline=structuredClone(examples);
let saved=structuredClone(examples),fail=false;
beforeEach(()=>{
 saved=structuredClone(baseline);fail=false;localStorage.clear();
 for(const key of ['bn-general','en-general'] as const){
  saved[key].source=excerpt;
  saved[key].result.sections.steps=[{text:excerpt,evidence_ids:['e1','e12'],source_conditions:[]}];
  saved[key].result.evidence=[{id:'e1',excerpt},{id:'e12',excerpt}];
 }
 Object.assign(examples,saved); // Inject hostile text into the bundled fixture, not a network response.
 vi.stubGlobal('fetch',vi.fn(async(input:unknown)=>{
  const path=String(input);
  if(path.endsWith('/api/health'))return new Response('{"status":"ok"}');
  if(path.includes('examples.json'))return new Response(JSON.stringify(saved));
  if(path.endsWith('/api/session'))return new Response('{"token":"offline"}');
  if(path.endsWith('/api/analysis'))return new Response('{"job_id":"offline-job"}',{status:202});
  if(path.endsWith('/api/jobs/offline-job')&&fail)return new Response('{"status":"failed","stage":"analyzing","error":"timeout"}');
  if(path.endsWith('/api/jobs/offline-job'))return new Response(JSON.stringify({status:'succeeded',result:saved[document.documentElement.lang==='en'?'en-general':'bn-general'].result}));
  throw Error('Unmocked bilingual request');
 }));
});
afterEach(()=>{Object.assign(examples,structuredClone(baseline));cleanup();vi.unstubAllGlobals();vi.restoreAllMocks()});

it('starts in Bangla with Ask selected and preserves independent drafts across language changes',async()=>{
 const user=userEvent.setup();render(<App/>);
 expect(screen.getByRole('button',{name:'English'}).getAttribute('lang')).toBe('en');
 expect(screen.getByRole('button',{name:'বাংলা'}).getAttribute('lang')).toBe('bn');
 expect(screen.getByRole('button',{name:ASK_COPY.bn.tab}).getAttribute('aria-pressed')).toBe('true');
 await user.click(screen.getByRole('button',{name:COPY.bn.link}));
 await user.type(screen.getByLabelText(COPY.bn.linkLabel),'https://example.gov.bd/a');
 await user.click(screen.getByRole('button',{name:'English'}));
 expect((screen.getByLabelText('Public page URL') as HTMLInputElement).value).toBe('https://example.gov.bd/a');
 await user.click(screen.getByRole('button',{name:COPY.en.text}));
 await user.type(screen.getByLabelText(COPY.en.paste),'Independent draft');
 await user.click(screen.getByRole('button',{name:'বাংলা'}));
 await user.click(screen.getByRole('button',{name:'English'}));
 expect((screen.getByLabelText(COPY.en.paste) as HTMLTextAreaElement).value).toBe('Independent draft');
 expect(vi.mocked(fetch).mock.calls.every(([path])=>String(path).endsWith('/api/health'))).toBe(true);
});

it.each(['bn','en'])('renders hostile source literally and keeps evidence IDs in %s copy/print',async(language)=>{
 const user=userEvent.setup();const {container}=render(<App/>);
 if(language==='en')await user.click(screen.getByRole('button',{name:'English'}));
 const c=COPY[language as 'bn'|'en'];await user.click(screen.getByRole('button',{name:c.text}));fireEvent.change(screen.getByLabelText(c.paste),{target:{value:excerpt}});await user.click(screen.getByRole('button',{name:c.continue}));await user.click(screen.getByRole('checkbox'));await user.click(screen.getByRole('button',{name:c.analyze}));
 await screen.findByRole('heading',{name:language==='en'?COPY.en.result:COPY.bn.result});
 const write=vi.spyOn(navigator.clipboard,'writeText').mockResolvedValue();
 expect(container.querySelectorAll('script')).toHaveLength(0);
 const quotes=Array.from(container.querySelectorAll('blockquote'));
 expect(quotes.filter(e=>e.textContent===excerpt).length).toBeGreaterThanOrEqual(2);
 expect(container.querySelector('.steps .claim p')?.getAttribute('lang')).toBe(language);
 expect(quotes.every(e=>e.getAttribute('lang')==='')).toBe(true);
 expect(container.querySelector('.original-source')?.textContent??container.textContent).toContain(excerpt);
 await user.click(screen.getByRole('button',{name:COPY[language as keyof typeof COPY].copy}));
 await waitFor(()=>expect(write).toHaveBeenCalledOnce());
 const summary=write.mock.calls[0][0];
 expect(summary).toContain(excerpt+' [e1, e12]');
 expect(summary).toContain('e12: '+excerpt);
 expect(container.querySelector('.print-evidence')?.textContent).toContain('[e12] '+excerpt);
 expect(container.querySelectorAll('script')).toHaveLength(0);
 await user.click(screen.getByRole('button',{name:language==='en'?'বাংলা':'English'}));
 expect(document.documentElement.lang).toBe(language==='en'?'bn':'en');
 expect(container.querySelector('.steps .claim p')?.getAttribute('lang')).toBe(language);
 expect(container.querySelector('.unknowns .uncertainty p')?.getAttribute('lang')).toBe(language);
});

it('translates a timeout without another submission and preserves the reviewed source',async()=>{
 const user=userEvent.setup();render(<App/>);fail=true;
 await user.click(screen.getByRole('button',{name:'English'}));
 await user.click(screen.getByRole('button',{name:COPY.en.text}));
 await user.type(screen.getByLabelText(COPY.en.paste),'A public notice.');
 await user.click(screen.getByRole('button',{name:'Review this text'}));
 await user.click(screen.getByRole('checkbox'));
 await user.click(screen.getByRole('button',{name:COPY.en.analyze}));
 await screen.findByRole('alert');
 const english=screen.getByRole('alert').textContent;
 const calls=vi.mocked(fetch).mock.calls.length;
 await user.click(screen.getByRole('button',{name:'বাংলা'}));
 expect(screen.getByRole('alert').textContent).not.toBe(english);
 expect((screen.getByRole('textbox') as HTMLTextAreaElement).value).toBe('A public notice.');
 expect(vi.mocked(fetch).mock.calls.length).toBe(calls);
 expect(vi.mocked(fetch).mock.calls.filter(([path])=>String(path).endsWith('/api/analysis'))).toHaveLength(1);
});
