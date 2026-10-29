import {useEffect,useRef,useState} from 'react';
import {ArrowLeft,ArrowRight} from 'lucide-react';
import {COPY,JOURNEY_COPY} from './uiCopy';

export function ResultNavigation({lang,example,onBack,onNew,backLabel,newPrompt}:{lang:'bn'|'en';example:boolean;onBack:()=>void;onNew:()=>void;backLabel?:string;newPrompt?:string}){
 const anchor=useRef<HTMLDivElement>(null);
 const keep=useRef<HTMLButtonElement>(null),start=useRef<HTMLButtonElement>(null),wasConfirming=useRef(false);
 const [floating,setFloating]=useState(false),[confirming,setConfirming]=useState(false);
 const c=COPY[lang],j=JOURNEY_COPY[lang];
 useEffect(()=>{
  if(confirming)keep.current?.focus();
  else if(wasConfirming.current)start.current?.focus();
  wasConfirming.current=confirming;
 },[confirming]);
 useEffect(()=>{
  if(!anchor.current||typeof IntersectionObserver==='undefined')return;
  const observer=new IntersectionObserver(([entry])=>setFloating(!entry.isIntersecting));
  observer.observe(anchor.current);return()=>observer.disconnect();
 },[]);
 return <div className="result-navigation-anchor" ref={anchor}>
  <nav aria-label={j.resultNavigation} className={'result-navigation'+(floating?' is-floating':'')} onKeyDown={e=>{if(confirming&&e.key==='Escape'){e.preventDefault();setConfirming(false)}}}>
   {confirming?<><p role="status">{newPrompt||j.resetPrompt}</p><div className="actions">
    <button ref={keep} className="secondary" onClick={()=>setConfirming(false)}>{j.keepResult}</button>
    <button className="primary" onClick={onNew}>{j.confirmNew}<ArrowRight size={17} aria-hidden="true"/></button>
   </div></>:<div className="actions">
    <button className="secondary" onClick={onBack}><ArrowLeft size={16} aria-hidden="true"/>{backLabel||(example?j.previous:c.edit)}</button>
    <button ref={start} className="primary" onClick={()=>example?onNew():setConfirming(true)}>{example?j.exit:c.new}<ArrowRight size={17} aria-hidden="true"/></button>
   </div>}
  </nav>
 </div>;
}
