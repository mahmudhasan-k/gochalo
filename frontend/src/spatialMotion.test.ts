import {afterEach,expect,it,vi} from 'vitest';
import type {PointerEvent} from 'react';
import {moveSpatialTilt,resetSpatialTilt} from './spatialMotion';

afterEach(()=>vi.unstubAllGlobals());
function pointer(pointerType='mouse'){
 const currentTarget=document.createElement('div');
 currentTarget.getBoundingClientRect=()=>({left:0,top:0,width:200,height:100} as DOMRect);
 return {currentTarget,pointerType,clientX:400,clientY:-100} as unknown as PointerEvent<HTMLElement>;
}
it('bounds tilt at the card edges and clears its spotlight on exit',()=>{
 vi.stubGlobal('matchMedia',vi.fn(()=>({matches:true})));
 const event=pointer();moveSpatialTilt(event);
 expect(event.currentTarget.style.getPropertyValue('--rx')).toBe('2.50deg');
 expect(event.currentTarget.style.getPropertyValue('--ry')).toBe('2.50deg');
 resetSpatialTilt(event);
 expect(event.currentTarget.style.getPropertyValue('--rx')).toBe('0deg');
 expect(event.currentTarget.style.getPropertyValue('--mx')).toBe('50%');
});
it('keeps reduced-motion, unsupported and touch input stationary',()=>{
 const event=pointer();vi.stubGlobal('matchMedia',vi.fn(()=>({matches:false})));
 moveSpatialTilt(event);expect(event.currentTarget.style.getPropertyValue('--ry')).toBe('0deg');
 vi.stubGlobal('matchMedia',undefined);moveSpatialTilt(event);
 expect(event.currentTarget.style.getPropertyValue('--rx')).toBe('0deg');
 vi.stubGlobal('matchMedia',vi.fn(()=>({matches:true})));
 const touch=pointer('touch');moveSpatialTilt(touch);
 expect(touch.currentTarget.style.getPropertyValue('--rx')).toBe('0deg');
});
