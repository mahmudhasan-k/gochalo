import {Calendar,Clock,Globe} from 'lucide-react';
import {Checkbox} from './WorkspaceControls';
import {useState} from 'react';
import {Modal} from './Modal';
import {downloadCalendar,validDate,type CalendarEntry} from './calendar';
import {PRODUCT_COPY} from './productCopy';
import type {Lang} from './productTypes';
export function CalendarPreview({entries,lang,onClose}:{entries:CalendarEntry[];lang:Lang;onClose:()=>void}){
 const c=PRODUCT_COPY[lang];const [drafts,setDrafts]=useState(entries.map(entry=>({...entry,selected:true}))),[error,setError]=useState(false);
 const selected=drafts.filter(entry=>entry.selected);const valid=selected.length>0&&selected.every(entry=>validDate(entry.date)&&entry.title.trim());
 return <Modal title={c.calendarTitle} onClose={onClose}><p>{c.calendarHelp}</p><form onSubmit={event=>{event.preventDefault();try{downloadCalendar(selected);onClose()}catch{setError(true)}}}>
 {drafts.map((entry,index)=><fieldset className="calendar-entry" key={entry.id}><legend><label><Checkbox checked={entry.selected} onChange={event=>setDrafts(rows=>rows.map((row,i)=>i===index?{...row,selected:event.target.checked}:row))}/>{entry.title}</label></legend>
 <label>{c.taskTitle}<input value={entry.title} required={entry.selected} maxLength={2000} onChange={event=>setDrafts(rows=>rows.map((row,i)=>i===index?{...row,title:event.target.value}:row))}/></label>
 <div className="form-row"><label>{c.date}<span className="picker-control"><Calendar size={16}/><input type="date" required={entry.selected} value={entry.date} onChange={event=>setDrafts(rows=>rows.map((row,i)=>i===index?{...row,date:event.target.value}:row))}/></span></label><label>{c.time}<span className="picker-control"><Clock size={16}/><input type="time" value={entry.time||''} onChange={event=>setDrafts(rows=>rows.map((row,i)=>i===index?{...row,time:event.target.value}:row))}/></span></label><label>{c.timezone}<span className="picker-control"><Globe size={16}/><select value={entry.timezone} onChange={event=>setDrafts(rows=>rows.map((row,i)=>i===index?{...row,timezone:event.target.value}:row))}><option>Asia/Dhaka</option><option>UTC</option></select></span></label></div></fieldset>)}
 {error&&<p role="alert">{c.error}</p>}<div className="button-row"><button className="primary" disabled={!valid}>{c.download}</button><button type="button" onClick={onClose}>{c.cancel}</button></div></form></Modal>;
}
