import {afterEach,expect,it,vi} from 'vitest';
import {act,cleanup,render,screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {ResultNavigation} from './ResultNavigation';
import {COPY,JOURNEY_COPY} from './uiCopy';

afterEach(()=>{cleanup();vi.unstubAllGlobals()});
it.each(['bn','en'] as const)('protects the existing result before starting another notice in %s',async lang=>{
 const user=userEvent.setup(),reset=vi.fn(),back=vi.fn(),j=JOURNEY_COPY[lang];
 render(<ResultNavigation lang={lang} example={false} onNew={reset} onBack={back}/>);
 await user.click(screen.getByRole('button',{name:COPY[lang].new}));
 expect(reset).not.toHaveBeenCalled();expect(screen.getByRole('status').textContent).toBe(j.resetPrompt);
 expect(document.activeElement).toBe(screen.getByRole('button',{name:j.keepResult}));
 await user.keyboard('{Escape}');expect(document.activeElement).toBe(screen.getByRole('button',{name:COPY[lang].new}));
 await user.click(screen.getByRole('button',{name:COPY[lang].new}));
 await user.click(screen.getByRole('button',{name:j.keepResult}));expect(reset).not.toHaveBeenCalled();
 await user.click(screen.getByRole('button',{name:COPY[lang].edit}));expect(back).toHaveBeenCalledOnce();
 await user.click(screen.getByRole('button',{name:COPY[lang].new}));
 await user.click(screen.getByRole('button',{name:j.confirmNew}));expect(reset).toHaveBeenCalledOnce();
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
