import {act,cleanup,fireEvent,render,screen} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {ImageDropzone,useTypewriter,ScheduleField} from './WorkspaceControls';
import {POLISH_COPY} from './uiCopy';
afterEach(()=>{cleanup();vi.useRealTimers();vi.unstubAllGlobals();vi.restoreAllMocks()});
function Placeholder({active=true,lang='en'}:{active?:boolean;lang?:'en'|'bn'}){const placeholder=useTypewriter(lang,active);return <input aria-label="Query" placeholder={placeholder}/>}
it('animates only when idle, stops on focus/input, and cleans up timers',()=>{
 vi.useFakeTimers();const view=render(<Placeholder/>);const input=screen.getByRole('textbox');
 act(()=>vi.advanceTimersByTime(55));expect(input.getAttribute('placeholder')).toBe('H');
 view.rerender(<Placeholder active={false}/>);expect(input.getAttribute('placeholder')).toBe('');expect(vi.getTimerCount()).toBe(0);
 act(()=>vi.advanceTimersByTime(2000));expect(input.getAttribute('placeholder')).toBe('');
 view.rerender(<Placeholder/>);act(()=>vi.advanceTimersByTime(55));expect(input.getAttribute('placeholder')).toBe('H');
 view.unmount();expect(vi.getTimerCount()).toBe(0);
});
it('uses a static localized example with reduced motion and reacts to preference changes',()=>{
 vi.useFakeTimers();let changed:()=>void=()=>{};const media={matches:true,addEventListener:vi.fn((_event,fn)=>{changed=fn}),removeEventListener:vi.fn()};
 vi.stubGlobal('matchMedia',()=>media);const view=render(<Placeholder lang="bn"/>);
 expect(screen.getByRole('textbox').getAttribute('placeholder')).toBe(POLISH_COPY.bn.examples[0]);expect(vi.getTimerCount()).toBe(0);
 media.matches=false;act(()=>changed());act(()=>vi.advanceTimersByTime(55));expect(screen.getByRole('textbox').getAttribute('placeholder')).toBe(POLISH_COPY.bn.examples[0].slice(0,1));
 view.unmount();expect(media.removeEventListener).toHaveBeenCalled();
});
it('validates dropped and browsed files, preserves the existing selection on rejection, and revokes previews',()=>{
 const create=vi.fn(()=> 'blob:preview'),revoke=vi.fn();vi.stubGlobal('URL',Object.assign(URL,{createObjectURL:create,revokeObjectURL:revoke}));
 const onFile=vi.fn(),file=new File(['image'],'notice.png',{type:'image/png'});const view=render(<ImageDropzone lang="en" disabled={false} file={file} onFile={onFile}/>);
 const input=screen.getByLabelText(POLISH_COPY.en.imageLabel),drop=input.closest('label')!;
 fireEvent.drop(drop,{dataTransfer:{files:[new File(['bad'],'bad.gif',{type:'image/gif'})]}});expect(onFile).not.toHaveBeenCalled();expect(screen.getByRole('alert').textContent).toBe(POLISH_COPY.en.imageError);
 fireEvent.change(input,{target:{files:[new File([new Uint8Array(5*1024*1024+1)],'large.png',{type:'image/png'})]}});expect(onFile).not.toHaveBeenCalled();
 fireEvent.drop(drop,{dataTransfer:{files:[file]}});expect(onFile).toHaveBeenCalledWith(file);
 view.rerender(<ImageDropzone lang="en" disabled file={file} onFile={onFile}/>);fireEvent.drop(drop,{dataTransfer:{files:[file]}});expect(onFile).toHaveBeenCalledTimes(1);
 view.unmount();expect(revoke).toHaveBeenCalledWith('blob:preview');
});

it.each(['date','time'] as const)('opens the %s picker from the whole scheduling field and preserves native input',type=>{
 const change=vi.fn();const view=render(<ScheduleField type={type} label="Schedule" onChange={change}/>);
 const field=screen.getByLabelText('Schedule') as HTMLInputElement;const picker=vi.fn();Object.defineProperty(field,'showPicker',{configurable:true,value:picker});
 fireEvent.click(field.closest('label')!);expect(picker).toHaveBeenCalledOnce();expect(document.activeElement).toBe(field);
 fireEvent.click(field);expect(picker).toHaveBeenCalledTimes(2);
 picker.mockImplementation(()=>{throw new DOMException('Picker unavailable')});fireEvent.click(field);
 fireEvent.change(field,{target:{value:type==='date'?'2026-11-02':'09:30'}});expect(change).toHaveBeenCalledOnce();
 view.rerender(<ScheduleField type={type} label="Schedule" disabled onChange={change}/>);picker.mockClear();fireEvent.click(field.closest('label')!);expect(picker).not.toHaveBeenCalled();
});