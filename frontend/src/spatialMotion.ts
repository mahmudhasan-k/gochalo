import type {PointerEvent} from 'react';

const motionQuery='(hover: hover) and (pointer: fine) and (prefers-reduced-motion: no-preference)';

export function resetSpatialTilt(event:PointerEvent<HTMLElement>){
 const style=event.currentTarget.style;
 style.setProperty('--rx','0deg');style.setProperty('--ry','0deg');
 style.setProperty('--mx','50%');style.setProperty('--my','50%');
}

export function moveSpatialTilt(event:PointerEvent<HTMLElement>){
 if(event.pointerType==='touch'||!window.matchMedia?.(motionQuery).matches){resetSpatialTilt(event);return;}
 const element=event.currentTarget,rect=element.getBoundingClientRect();
 if(!rect.width||!rect.height)return;
 const x=Math.max(0,Math.min(1,(event.clientX-rect.left)/rect.width));
 const y=Math.max(0,Math.min(1,(event.clientY-rect.top)/rect.height));
 element.style.setProperty('--rx',((.5-y)*5).toFixed(2)+'deg');
 element.style.setProperty('--ry',((x-.5)*5).toFixed(2)+'deg');
 element.style.setProperty('--mx',(x*100).toFixed(2)+'%');
 element.style.setProperty('--my',(y*100).toFixed(2)+'%');
}
