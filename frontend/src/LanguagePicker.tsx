import {useEffect,useId,useRef,useState} from 'react';
import {Check} from 'lucide-react';
import type {Lang} from './productTypes';
export function LanguagePicker({lang,onChange,disabled=false}:{lang:Lang;onChange:(value:Lang)=>void;disabled?:boolean}){
 const [open,setOpen]=useState(false),root=useRef<HTMLDivElement>(null),trigger=useRef<HTMLButtonElement>(null),id=useId();
 const label=lang==='bn'?'ভাষা':'Language';
 const close=()=>{setOpen(false);trigger.current?.focus()};
 useEffect(()=>{if(!open)return;root.current?.querySelector<HTMLButtonElement>('[aria-checked="true"]')?.focus();const outside=(event:PointerEvent)=>{if(!root.current?.contains(event.target as Node))setOpen(false)};document.addEventListener('pointerdown',outside);return()=>document.removeEventListener('pointerdown',outside)},[open]);
 useEffect(()=>{if(disabled)setOpen(false)},[disabled]);
 return <div className="language-picker" ref={root} onBlur={event=>{if(event.relatedTarget&&!event.currentTarget.contains(event.relatedTarget))setOpen(false)}} onKeyDown={event=>{
  if(event.key==='Escape'&&open){event.preventDefault();close()}
  if(!open&&['ArrowDown','ArrowUp'].includes(event.key)){event.preventDefault();setOpen(true);return}
  if(open&&['ArrowDown','ArrowUp','Home','End'].includes(event.key)){event.preventDefault();const items=Array.from(root.current!.querySelectorAll<HTMLButtonElement>('[role="menuitemradio"]'));const current=items.indexOf(document.activeElement as HTMLButtonElement);const next=event.key==='Home'?0:event.key==='End'?items.length-1:(current+(event.key==='ArrowDown'?1:-1)+items.length)%items.length;items[next]?.focus()}
 }}>
 <button className="language-trigger" ref={trigger} aria-haspopup="menu" aria-expanded={open} aria-controls={id} disabled={disabled} onClick={()=>setOpen(!open)}><span id={id+'-selection'} className="sr-only">{label}: {lang==='bn'?'বাংলা':'English'} </span><span className={'language-choice'+(lang==='en'?' active':'')}>EN</span><span className="language-divider" aria-hidden="true"/><span className={'language-choice'+(lang==='bn'?' active':'')}>BN</span></button>
 {open&&<div className="language-popover" id={id}><p className="language-menu-label">{label}</p><div role="menu" aria-label={label}>{(['en','bn'] as Lang[]).map(value=><button key={value} type="button" role="menuitemradio" aria-checked={lang===value} onClick={()=>{onChange(value);close()}}><span lang={value}>{value==='bn'?'বাংলা':'English'}</span>{lang===value&&<Check size={16} aria-hidden="true"/>}</button>)}</div></div>}
 </div>;
}
