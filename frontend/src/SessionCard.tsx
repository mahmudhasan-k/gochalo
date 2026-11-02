import {useState} from 'react';
import {ArrowUpRight,Trash2,Pencil,ScanLine,Link,AlignLeft,Sparkles} from 'lucide-react';
import {PRODUCT_COPY} from './productCopy';
import {formatCreated} from './sessionDate';
import type {Lang,Retrieval} from './productTypes';
export function sessionPreview(row:Retrieval){
 const text=row.result.sections.explanation?.[0]?.text||row.input;
 return text.replace(/!\[[^\]]*\]\([^)]*\)/g,'').replace(/\[([^\]]*)\]\([^)]*\)/g,'$1').replace(/<[^>]*>/g,'').replace(/^[\t ]*#{1,6}\s+/gm,'').replace(/[\[\]`*_]/g,'').replace(/\s+/g,' ').trim().slice(0,140);
}
export function SessionCard({row,lang,onOpen,onDelete,onRename}:{row:Retrieval;lang:Lang;onOpen:()=>void;onDelete:()=>void;onRename:(title:string)=>void}){
 const c=PRODUCT_COPY[lang],Icon=row.kind==='image'?ScanLine:row.kind==='link'?Link:row.kind==='text'?AlignLeft:Sparkles;const [editing,setEditing]=useState(false),[title,setTitle]=useState(row.title);
 function commit(){if(title.trim()&&title.trim()!==row.title)onRename(title.trim());setEditing(false)}
 return <article className="retrieval-card"><div className="session-card-heading"><span className="eyebrow">{row.kind==='research'?'WEB':row.kind==='ask'?'PLAN':'SOURCE'}</span><div className="session-card-controls"><button className="quiet" aria-label={c.rename+': '+row.title} onClick={()=>{setTitle(row.title);setEditing(true)}}><Pencil size={15}/></button><button className="quiet" aria-label={c.delete+': '+row.title} onClick={onDelete}><Trash2 size={16}/></button></div></div>
 {editing?<input autoFocus aria-label={c.rename} value={title} maxLength={160} onChange={event=>setTitle(event.target.value)} onBlur={commit} onKeyDown={event=>{if(event.key==='Enter'&&!event.nativeEvent.isComposing){event.preventDefault();commit()}if(event.key==='Escape'){event.preventDefault();setEditing(false)}}}/>:<button className="card-open" onClick={onOpen}><div className="session-card-identity"><span className="session-source-icon" aria-hidden="true"><Icon size={16}/></span><div className="session-card-content"><h3>{row.title}</h3><p>{sessionPreview(row)}</p><small><time dateTime={row.createdAt}>{formatCreated(row.createdAt,lang)}</time><ArrowUpRight size={15}/></small></div></div></button>}</article>;
}
