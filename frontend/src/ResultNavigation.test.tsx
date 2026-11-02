import {afterEach,expect,it,vi} from 'vitest';
import {act,cleanup,render,screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {ResultNavigation} from './ResultNavigation';
import {COPY,JOURNEY_COPY} from './uiCopy';

afterEach(()=>{cleanup();vi.unstubAllGlobals()});
it.each(['bn','en'] as const)('shows the warning and starts another plan on one click in %s',async lang=>{
 const user=userEvent.setup(),reset=vi.fn(),back=vi.fn(),j=JOURNEY_COPY[lang];
 render(<ResultNavigation lang={lang} example={false} onNew={reset} onBack={back}/>);
 expect(screen.getByText(j.resetPrompt)).toBeTruthy();
 const start=screen.getByRole('button',{name:COPY[lang].new});
 expect(start.getAttribute('aria-describedby')).toBe(screen.getByText(j.resetPrompt).id);
 await user.click(start);expect(reset).toHaveBeenCalledOnce();
 expect(screen.queryByRole('button',{name:j.keepResult})).toBeNull();
 await user.click(screen.getByRole('button',{name:COPY[lang].edit}));expect(back).toHaveBeenCalledOnce();
});
it('floats one set of controls until its footer is visible and disconnects on exit',()=>{
 let notify:(entries:{isIntersecting:boolean}[])=>void=()=>{};
 const disconnect=vi.fn(),observe=vi.fn();
 vi.stubGlobal('IntersectionObserver',class {constructor(callback:typeof notify){notify=callback}observe=observe;disconnect=disconnect});
 const view=render(<ResultNavigation lang="en" example={false} onNew={()=>{}} onBack={()=>{}}/>);
 act(()=>notify([{isIntersecting:false}]));expect(view.container.querySelector('.is-floating')).toBeTruthy();
 expect(screen.getAllByRole('button',{name:COPY.en.new})).toHaveLength(1);
 act(()=>notify([{isIntersecting:true}]));expect(view.container.querySelector('.is-floating')).toBeNull();
 view.unmount();expect(disconnect).toHaveBeenCalledOnce();
});
