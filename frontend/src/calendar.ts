export type CalendarEntry={id:string;title:string;date:string;time?:string;timezone:string;description?:string};
export function explicitDate(text:string){
 const normalized=text.replace(/[০-৯]/g,char=>String('০১২৩৪৫৬৭৮৯'.indexOf(char)));
 const match=normalized.match(/\b(\d{4}-\d{2}-\d{2})\b/);return match&&validDate(match[1])?match[1]:'';
}
export function validDate(value:string){return /^\d{4}-\d{2}-\d{2}$/.test(value)&&!Number.isNaN(Date.parse(value+'T00:00:00Z'))&&new Date(value+'T00:00:00Z').toISOString().slice(0,10)===value}
const escape=(value:string)=>value.replace(/\\/g,'\\\\').replace(/\r\n|\r|\n/g,'\\n').replace(/;/g,'\\;').replace(/,/g,'\\,');
function fold(line:string){let output='',bytes=0;for(const char of line){const size=new TextEncoder().encode(char).length;if(bytes+size>75){output+='\r\n ';bytes=1}output+=char;bytes+=size}return output}
function utcStamp(date:Date){return date.toISOString().replace(/[-:]/g,'').replace(/\.\d{3}Z$/,'Z')}
export function buildCalendar(entries:CalendarEntry[],now=new Date()){
 const lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Gochalo//Calendar Export//EN','CALSCALE:GREGORIAN'];
 for(const entry of entries){
  if(!validDate(entry.date)||!entry.title.trim())throw new Error('calendar_invalid');
  lines.push('BEGIN:VEVENT','UID:'+escape(entry.id)+'@gochalo','DTSTAMP:'+utcStamp(now),'SUMMARY:'+escape(entry.title));
  if(entry.time){
   if(!/^([01]\d|2[0-3]):[0-5]\d$/.test(entry.time))throw new Error('calendar_invalid');
   // The first version offers explicit UTC or Bangladesh time; no guessed DST.
   if(!['Asia/Dhaka','UTC'].includes(entry.timezone))throw new Error('calendar_timezone');
   const start=new Date(entry.date+'T'+entry.time+':00'+(entry.timezone==='UTC'?'Z':'+06:00'));
   lines.push('DTSTART:'+utcStamp(start),'DTEND:'+utcStamp(new Date(start.getTime()+30*60000)));
  }else{
   const next=new Date(entry.date+'T00:00:00Z');next.setUTCDate(next.getUTCDate()+1);
   lines.push('DTSTART;VALUE=DATE:'+entry.date.replaceAll('-',''),'DTEND;VALUE=DATE:'+next.toISOString().slice(0,10).replaceAll('-',''));
  }
  if(entry.description)lines.push('DESCRIPTION:'+escape(entry.description));
  lines.push('END:VEVENT');
 }
 return [...lines,'END:VCALENDAR'].map(fold).join('\r\n')+'\r\n';
}
export function downloadCalendar(entries:CalendarEntry[]){const url=URL.createObjectURL(new Blob([buildCalendar(entries)],{type:'text/calendar;charset=utf-8'}));const link=document.createElement('a');link.href=url;link.download='gochalo-calendar.ics';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
