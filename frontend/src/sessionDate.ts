import type {Lang} from './productTypes';
export function formatCreated(value:string,lang:Lang){
 const date=new Date(value);if(Number.isNaN(date.getTime()))return '';
 const locale=lang==='bn'?'bn-BD':'en-GB';
 const day=new Intl.DateTimeFormat(locale,{day:'numeric',month:'long',year:'numeric'}).format(date);
 const time=new Intl.DateTimeFormat(locale,{hour:'numeric',minute:'2-digit',hour12:true}).format(date).replace(/ (am|pm)$/i,(_,period:string)=>period.toLowerCase());
 return day+' · '+time;
}
