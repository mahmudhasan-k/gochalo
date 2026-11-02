import {useEffect,useId,useRef,useState} from 'react';
import {ArrowLeft,ArrowRight} from 'lucide-react';
import {COPY,JOURNEY_COPY} from './uiCopy';

export function ResultNavigation({lang,example,onBack,onNew,backLabel,newPrompt}:{lang:'bn'|'en';example:boolean;onBack:()=>void;onNew:()=>void;backLabel?:string;newPrompt?:string}){
 const anchor=useRef<HTMLDivElement>(null),warningId=useId();
 const [floating,setFloating]=useState(false);
 const c=COPY[lang],j=JOURNEY_COPY[lang];
 useEffect(()=>{
  if(!anchor.current||typeof IntersectionObserver==='undefined')return;
  const observer=new IntersectionObserver(([entry])=>setFloating(!entry.isIntersecting));
  observer.observe(anchor.current);return()=>observer.disconnect();
 },[]);
 return <div className="result-navigation-anchor" ref={anchor}>
  <nav aria-label={j.resultNavigation} className={'result-navigation'+(floating?' is-floating':'')}>
   {!example&&<p id={warningId} className="new-plan-warning">{newPrompt||j.resetPrompt}</p>}
   <div className="actions">
    <button className="secondary" onClick={onBack}><ArrowLeft size={16} aria-hidden="true"/>{backLabel||(example?j.previous:c.edit)}</button>
    <button className="primary" aria-describedby={example?undefined:warningId} onClick={onNew}>{example?j.exit:c.new}<ArrowRight size={17} aria-hidden="true"/></button>
   </div>
  </nav>
 </div>;
}
