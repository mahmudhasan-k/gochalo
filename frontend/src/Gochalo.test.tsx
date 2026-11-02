import {webcrypto} from 'node:crypto';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {App} from '../legacy/LegacyJourney';
import {ASK_COPY,COPY,pageTitle} from './uiCopy';
import {completionLabel} from './resultPresentation';
import examples from '../public/examples.json';

const source=examples['en-general'].source;
let result:any;
beforeEach(()=>{
 localStorage.clear();
 result={...structuredClone(examples['en-general'].result),demo:false,review_mode:'deterministic_only'};
 vi.stubGlobal('crypto',{randomUUID:()=>webcrypto.randomUUID(),subtle:webcrypto.subtle});
 vi.stubGlobal('fetch',vi.fn(async(input:unknown)=>{
  const path=String(input);
  if(path.endsWith('/api/health'))return new Response('{"status":"ok"}');
  if(path.endsWith('/api/session'))return new Response('{"token":"offline"}');
  if(path.endsWith('/api/analysis'))return new Response('{"job_id":"fixture"}',{status:202});
  if(path.endsWith('/api/jobs/fixture'))return new Response(JSON.stringify({status:'succeeded',result}));
  throw new Error('Unexpected offline fixture request: '+path);
 }));
});
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals();localStorage.clear()});

it.each(['bn','en'] as const)('brands the entry, defaults to Ask and keeps the correct journey stages in %s',async lang=>{
 const user=userEvent.setup();const {container}=render(<App initialLanguage={lang}/>);const c=COPY[lang];
 expect(container.querySelector('.brand')?.textContent).toContain(c.brand);
 expect(container.querySelector('footer')?.textContent).toContain(c.brand);
 expect(screen.getByText(c.intro)).toBeTruthy();
 const modes=within(screen.getByRole('group',{name:c.input})).getAllByRole('button');
 expect(modes.map(button=>button.textContent)).toEqual([ASK_COPY[lang].tab,c.image,c.link,c.text]);
 expect(modes[0].getAttribute('aria-pressed')).toBe('true');
 expect(container.querySelectorAll('.progress li')).toHaveLength(2);
 expect(document.title).toBe(pageTitle(location.hostname));
 expect(document.title).toContain('গোছালো — Gochalo');
 expect(container.textContent).not.toMatch(/Shobuj Potro|সবুজ পত্র/);
 await user.click(modes[2]);expect(container.querySelectorAll('.progress li')).toHaveLength(3);
});

async function openNotice(user:ReturnType<typeof userEvent.setup>){
 await user.click(screen.getByRole('button',{name:COPY.en.text}));
 fireEvent.change(screen.getByLabelText(COPY.en.paste),{target:{value:source}});
 await user.click(screen.getByRole('button',{name:COPY.en.continue}));
 await user.click(screen.getByRole('checkbox'));
 await user.click(screen.getByRole('button',{name:COPY.en.analyze}));
 await screen.findByRole('heading',{name:COPY.en.result});
 if(screen.queryAllByRole('checkbox').length)await waitFor(()=>expect((screen.getAllByRole('checkbox')[0] as HTMLInputElement).disabled).toBe(false));
}

it('tracks each checklist independently, restores progress and localizes reset state',async()=>{
 const user=userEvent.setup();const first=render(<App initialLanguage="en"/>);await openNotice(user);
 const actions=screen.getByRole('progressbar',{name:COPY.en.steps});
 const prep=screen.getByRole('progressbar',{name:COPY.en.documents});
 expect(actions.getAttribute('aria-valuenow')).toBe('0');expect(prep.getAttribute('aria-valuenow')).toBe('0');
 const checks=screen.getAllByRole('checkbox');await user.click(checks[0]);
 expect(actions.getAttribute('aria-valuenow')).toBe('1');expect(prep.getAttribute('aria-valuenow')).toBe('0');
 await user.click(checks[result.sections.steps.length]);
 expect(prep.getAttribute('aria-valuenow')).toBe('1');
 expect(prep.getAttribute('aria-valuetext')).toBe(completionLabel(1,result.sections.documents.length,'en'));
 first.unmount();render(<App initialLanguage="en"/>);await openNotice(user);
 await waitFor(()=>expect(screen.getByRole('progressbar',{name:COPY.en.steps}).getAttribute('aria-valuenow')).toBe('1'));
 expect(screen.getByRole('progressbar',{name:COPY.en.documents}).getAttribute('aria-valuenow')).toBe('1');
 await user.click(screen.getByRole('button',{name:'বাংলা'}));
 expect(screen.getByRole('progressbar',{name:COPY.bn.steps}).getAttribute('aria-valuetext')).toBe(completionLabel(1,result.sections.steps.length,'bn'));
 await user.click(screen.getByRole('button',{name:COPY.bn.resetChecklist}));
 for(const bar of screen.getAllByRole('progressbar'))expect(bar.getAttribute('aria-valuenow')).toBe('0');
});

it('brands copied and printable plans while retaining warnings, conditions and exact source',async()=>{
 const user=userEvent.setup();const {container}=render(<App initialLanguage="en"/>);await openNotice(user);
 const clipboard=vi.spyOn(navigator.clipboard,'writeText').mockResolvedValue();
 await user.click(screen.getByRole('button',{name:COPY.en.copy}));
 const summary=clipboard.mock.calls[0][0];expect(summary.startsWith('Gochalo\n')).toBe(true);
 for(const text of [COPY.en.steps,COPY.en.documents,COPY.en.deterministicWarning,source])expect(summary).toContain(text);
 for(const quote of result.evidence)expect(summary).toContain(quote.excerpt);
 expect(container.querySelector('.print-brand')?.textContent).toContain('Gochalo');
 expect(container.querySelector('.review-warning')?.textContent).toBe(COPY.en.deterministicWarning);
 for(const marker of container.querySelectorAll('.checklist-row'))expect(marker.getAttribute('data-print-marker')).toBe('[ ]');
});

it('omits progress bars for empty sections and preserves the prepared example completion',async()=>{
 result.sections.steps=[];result.sections.documents=[];
 const user=userEvent.setup();const view=render(<App initialLanguage="en"/>);await openNotice(user);
 expect(screen.queryAllByRole('progressbar')).toHaveLength(0);
 view.unmount();render(<App journeyMode="example" initialLanguage="en"/>);
 await user.click(screen.getByRole('button',{name:'Next step'}));await user.click(screen.getByRole('button',{name:'Next step'}));
 expect(screen.getByRole('progressbar',{name:COPY.en.steps}).getAttribute('aria-valuenow')).toBe('1');
 expect(screen.getByRole('progressbar',{name:COPY.en.documents}).getAttribute('aria-valuenow')).toBe('0');
});

it('starts a fresh plan in Ask with one click',async()=>{
 const user=userEvent.setup();render(<App initialLanguage="en"/>);await openNotice(user);
 await user.click(screen.getByRole('button',{name:COPY.en.new}));

 expect(screen.getByRole('button',{name:ASK_COPY.en.tab}).getAttribute('aria-pressed')).toBe('true');
 expect((screen.getByLabelText(ASK_COPY.en.input) as HTMLTextAreaElement).value).toBe('');
 expect(screen.queryByRole('heading',{name:COPY.en.result})).toBeNull();
});
