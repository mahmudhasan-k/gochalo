import {useEffect,useLayoutEffect,useRef,useState,type InputHTMLAttributes,type TextareaHTMLAttributes} from 'react';
import {Check,UploadCloud,Calendar,Clock} from 'lucide-react';
import {POLISH_COPY} from './uiCopy';
import type {Lang} from './productTypes';

export function Checkbox(props:InputHTMLAttributes<HTMLInputElement>){
 return <span className="checkbox-target"><input {...props} type="checkbox"/><span className="checkbox-box" aria-hidden="true"><Check size={14}/></span></span>;
}
const SCHEDULE_COPY={en:{date:'Date',time:'Time'},bn:{date:'তারিখ',time:'সময়'}};
export function ScheduleField({type,label,lang='en',...props}:Omit<InputHTMLAttributes<HTMLInputElement>,'type'> & {type:'date'|'time';label:string;lang?:Lang}){
 const ref=useRef<HTMLInputElement>(null),Icon=type==='date'?Calendar:Clock;
 return <label className={"schedule-field"+(!props.value?" is-empty":"")} title={label} onClick={event=>{const field=ref.current;if(!field||field.disabled)return;if(event.target!==field)event.preventDefault();field.focus();try{field.showPicker?.()}catch{/* Native text entry remains available when a browser cannot open its picker. */}}}>
  <Icon size={14} aria-hidden="true"/>{!props.value&&<span className="schedule-placeholder" aria-hidden="true">{SCHEDULE_COPY[lang][type]}</span>}<input {...props} ref={ref} type={type} aria-label={label}/>
 </label>;
}
export function TaskTitle(props:TextareaHTMLAttributes<HTMLTextAreaElement>){
 const ref=useRef<HTMLTextAreaElement>(null);
 useLayoutEffect(()=>{
  const field=ref.current;if(!field)return;
  const fit=()=>{field.style.height='0px';field.style.height=field.scrollHeight+'px'};
  let width=field.clientWidth;fit();
  const observer=typeof ResizeObserver==='undefined'?null:new ResizeObserver(()=>{if(width!==field.clientWidth){width=field.clientWidth;fit()}});
  observer?.observe(field);return()=>observer?.disconnect();
 },[props.value]);
 return <textarea {...props} className="task-title" rows={1} ref={ref}/>;
}
export function ChecklistProgress({done,total,label}:{done:number;total:number;label:string}){
 return <div className="checklist-progress" role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={total||1} aria-valuenow={done}><span style={{width:(total?100*done/total:0)+'%'}}/></div>;
}
export function useTypewriter(lang:Lang,active:boolean){
 const [reduced,setReduced]=useState(()=>window.matchMedia?.('(prefers-reduced-motion: reduce)').matches??false);
 const [frame,setFrame]=useState({example:0,length:0,deleting:false});
 const examples=POLISH_COPY[lang].examples;
 useEffect(()=>{const media=window.matchMedia?.('(prefers-reduced-motion: reduce)');if(!media)return;const change=()=>setReduced(media.matches);media.addEventListener('change',change);return()=>media.removeEventListener('change',change)},[]);
 useEffect(()=>setFrame({example:0,length:0,deleting:false}),[lang,active]);
 useEffect(()=>{if(!active||reduced)return;const text=examples[frame.example];const delay=frame.deleting?14:frame.length===text.length?1600:28;const timer=setTimeout(()=>setFrame(previous=>previous.deleting?(previous.length?{...previous,length:previous.length-1}:{example:(previous.example+1)%examples.length,length:0,deleting:false}):previous.length===text.length?{...previous,deleting:true}:{...previous,length:previous.length+1}),delay);return()=>clearTimeout(timer)},[active,reduced,examples,frame]);
 return !active?'':reduced?examples[0]:examples[frame.example].slice(0,frame.length);
}
export function ImageDropzone({file,disabled,lang,onFile}:{file:File|null;disabled:boolean;lang:Lang;onFile:(file:File|null)=>void}){
 const c=POLISH_COPY[lang];const [preview,setPreview]=useState(''),[error,setError]=useState(''),[dragging,setDragging]=useState(false);
 useEffect(()=>{if(!file||!URL.createObjectURL){setPreview('');return}const url=URL.createObjectURL(file);setPreview(url);return()=>URL.revokeObjectURL(url)},[file]);
 function select(next:File|null){setDragging(false);if(disabled)return;if(!next)return;if(!['image/png','image/jpeg'].includes(next.type)||next.size>5*1024*1024){setError(c.imageError);return}setError('');onFile(next)}
 return <div className="upload-area"><label className={'upload'+(dragging?' is-dragging':'')} onDragOver={event=>{event.preventDefault();if(!disabled)setDragging(true)}} onDragLeave={()=>setDragging(false)} onDrop={event=>{event.preventDefault();select(event.dataTransfer.files[0]||null)}}>
  <input className="upload-file" aria-label={c.imageLabel} type="file" accept="image/png,image/jpeg" disabled={disabled} onChange={event=>{select(event.target.files?.[0]||null);event.target.value=''}}/>
  <UploadCloud size={28} aria-hidden="true"/><strong>{c.upload}</strong><small>{c.uploadHint}</small>{file&&<span className="upload-name">{file.name}</span>}
 </label>{preview&&<img className="upload-preview" src={preview} alt={c.preview}/>} {error&&<p role="alert" className="notice warning">{error}</p>}</div>;
}
