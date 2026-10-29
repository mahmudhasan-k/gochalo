import type {Unknown,SectionState} from './resultPresentation';
export type Lang='bn'|'en';
export type InputKind='research'|'ask'|'image'|'link'|'text';
export type Claim={text:string;evidence_ids:string[];source_conditions?:string[];source_ids?:string[];support_ids?:string[];support_status?:'web_cited'|'planning_suggestion'|'unreviewed'|'source_supported'};
export type PlanResult={category_order?:string[];category_states?:Record<string,SectionState>;title?:string;review_mode?:'ai_reviewed'|'deterministic_only'|'saved_example'|'general_ask'|'web_research';semantic_review_complete?:boolean;source_reviewed?:boolean;sections:Record<string,Claim[]>;evidence:{id:string;excerpt:string}[];unknowns:Unknown[];section_states?:Record<string,SectionState>;withheld_count:number;partial:boolean;demo:boolean;has_guidance:boolean;sources?:{id:string;url:string;title:string}[];citation_supports?:{id:string;text:string;source_ids:string[]}[];searched_at?:string;search_attribution?:string};
export type Retrieval={schemaVersion:1;id:string;title:string;input:string;kind:InputKind;context:string;language:Lang;result:PlanResult;sourceUrl:string;returnedUrl:string;extractedOriginal:string;retrievedAt:string;createdAt:string;updatedAt:string;revision:number;deleted:boolean};
export type Task={schemaVersion:1;id:string;retrievalId:string;origin:string|null;title:string;completed:boolean;saved:boolean;dueDate:string;dueTime?:string;dueTimezone?:string;createdAt:string;updatedAt:string;revision:number;deleted:boolean};
export type RecordType='retrievals'|'tasks';
export type ContentRecord=Retrieval|Task;
export type Operation={id:string;table:RecordType;recordId:string;patch:Partial<ContentRecord>;baseRevision:number;createdAt:string};
export type WorkspaceData={retrievals:Retrieval[];tasks:Task[];outbox:Operation[];claims?:Record<string,string>};
export const emptyData=():WorkspaceData=>({retrievals:[],tasks:[],outbox:[]});
export function sourcePlanTitle(input:Pick<Retrieval,'kind'|'language'|'input'|'result'>){
 const clean=(value:string)=>value.replace(/!\[[^\]]*\]\([^)]*\)/g,'').replace(/\[([^\]]*)\]\([^)]*\)/g,'$1').replace(/https?:\/\/\S+/g,'').replace(/<[^>]*>/g,'').replace(/^[\s#*>|`_=-]+/,'').replace(/[\[\]`*_]/g,'').replace(/\s+/g,' ').trim();
 const lines=input.input.split(/\r?\n/);
 const heading=lines.find(line=>/^#{1,6}\s+/.test(line)&&clean(line).length>7);
 const topic=clean(input.result.title||heading||lines.find(line=>clean(line).length>12)||'').slice(0,100);
 const mode=input.kind==='link'?'URL':input.kind==='image'?'Image':'Text';
 const prefix=input.language==='bn'?({URL:'লিংক থেকে নেওয়া',Image:'ছবি থেকে নেওয়া',Text:'লেখা থেকে নেওয়া'}[mode]):'Extracted from '+mode;
 return prefix+(topic?' — '+topic:'');
}
export function createRetrieval(input:Partial<Retrieval>&Pick<Retrieval,'input'|'kind'|'language'|'result'>):Retrieval{
 const now=new Date().toISOString();return {schemaVersion:1,id:crypto.randomUUID(),title:['link','image','text'].includes(input.kind)?sourcePlanTitle(input):input.result.title||input.input.replace(/\s+/g,' ').slice(0,80),context:'',sourceUrl:'',returnedUrl:'',extractedOriginal:'',retrievedAt:'',createdAt:now,updatedAt:now,revision:0,deleted:false,...input};
}
export function candidateTasks(retrieval:Retrieval):Task[]{
 return ['steps','documents'].flatMap(section=>(retrieval.result.sections[section]||[]).map((item,index)=>({schemaVersion:1 as const,id:crypto.randomUUID(),retrievalId:retrieval.id,origin:`${section}:${index}`,title:item.text,completed:false,saved:false,dueDate:'',createdAt:retrieval.createdAt,updatedAt:retrieval.createdAt,revision:0,deleted:false})));
}

export function taskOrder(a:Task,b:Task){
 const position=(task:Task)=>task.origin?.startsWith('steps:')?[0,Number(task.origin.split(':')[1])]:task.origin?.startsWith('documents:')?[1,Number(task.origin.split(':')[1])]:[2,0];
 const left=position(a),right=position(b);
 return left[0]-right[0]||left[1]-right[1]||a.createdAt.localeCompare(b.createdAt)||a.id.localeCompare(b.id);
}
