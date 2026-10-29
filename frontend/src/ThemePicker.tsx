import {useEffect,useId,useRef,useState} from 'react';
import {Moon,Sun,Monitor,ChevronDown} from 'lucide-react';
import {JOURNEY_COPY} from './uiCopy';
import type {useTheme,ThemePreference} from './useTheme';
export function ThemePicker({lang,theme}:{lang:'bn'|'en';theme:ReturnType<typeof useTheme>}){
 const [open,setOpen]=useState(false),root=useRef<HTMLDivElement>(null),trigger=useRef<HTMLButtonElement>(null),id=useId();
 const bn=lang==='bn',c=JOURNEY_COPY[lang],Icon=theme.preference==='system'?Monitor:theme.resolved==='dark'?Moon:Sun;
 const close=()=>{setOpen(false);trigger.current?.focus()};
 useEffect(()=>{if(!open)return;root.current?.querySelector<HTMLInputElement>('input:checked')?.focus();const outside=(e:PointerEvent)=>{if(!root.current?.contains(e.target as Node))setOpen(false)};document.addEventListener('pointerdown',outside);return()=>document.removeEventListener('pointerdown',outside)},[open]);
 return <div className="theme-picker" ref={root} onKeyDown={e=>{if(e.key==='Escape'){e.preventDefault();close()}}} onBlur={e=>{if(e.relatedTarget&&!e.currentTarget.contains(e.relatedTarget))setOpen(false)}}>
 <button className="theme-trigger" ref={trigger} aria-label={(bn?'চেহারা: ':'Appearance: ')+(theme.preference==='system'?c.system:theme.resolved==='dark'?c.dark:c.light)} title={bn?'চেহারা':'Appearance'} aria-expanded={open} aria-controls={id} onClick={()=>setOpen(!open)}><Icon size={14} aria-hidden="true"/><span className="theme-label">{theme.preference==='system'?c.system:theme.resolved==='dark'?c.dark:c.light}</span><ChevronDown size={13} aria-hidden="true" className={open?'theme-chevron open':'theme-chevron'}/></button>
 {open&&<div className="theme-popover" id={id}><fieldset><legend>{bn?'চেহারা':'Appearance'}</legend>{(['system','light','dark'] as ThemePreference[]).map((v,i)=><label title={[c.system,c.light,c.dark][i]+(v==='system'?' — '+(theme.resolved==='dark'?c.dark:c.light):'')} className="theme-option" data-selected={theme.preference===v} key={v}><input type="radio" name={id} value={v} checked={theme.preference===v} onClick={close} onChange={()=>theme.setPreference(v)}/><span className="theme-option-icon" aria-hidden="true">{v==='system'?<Monitor size={17}/>:v==='light'?<Sun size={17}/>:<Moon size={17}/>}</span><span className="sr-only">{[c.system,c.light,c.dark][i]}</span></label>)}</fieldset></div>}
 </div>
}
