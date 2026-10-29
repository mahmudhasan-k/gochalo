import {COPY} from './uiCopy';
export type Category='documents'|'deadlines'|'fees'|'eligibility'|'steps'|'general';
export type SectionState='available'|'partial'|'not_stated'|'unconfirmed';
export type Unknown={kind:string;text:string;evidence_ids:string[];category?:Category;reason_code?:string};
const order:Category[]=['documents','deadlines','fees','eligibility','steps','general'];
const labels={bn:{documents:COPY.bn.documents,deadlines:COPY.bn.deadlines,fees:COPY.bn.fees,eligibility:'আবেদনের যোগ্যতা',steps:COPY.bn.steps,general:'অন্যান্য তথ্য'},en:{documents:COPY.en.documents,deadlines:COPY.en.deadlines,fees:COPY.en.fees,eligibility:'Eligibility',steps:COPY.en.steps,general:'Other information'}};
const groups={bn:{contradiction:'তথ্যে বিরোধ বা অসামঞ্জস্য',missing:'এগিয়ে যেতে যে তথ্যগুলো জানা প্রয়োজন',unverified:'যে তথ্যগুলো নিশ্চিত করা যায়নি'},en:{contradiction:'Conflicting information',missing:'Information needed to proceed',unverified:'Information we could not confirm'}};
export function uncertaintyGroups(items:Unknown[],lang:'bn'|'en'){
 return (['missing','contradiction','unverified'] as const).map(kind=>({kind,title:groups[lang][kind],items:items.filter(u=>u.kind===kind||kind==='unverified'&&!['missing','contradiction','unverified'].includes(u.kind)).slice().sort((a,b)=>order.indexOf(a.category||'general')-order.indexOf(b.category||'general'))})).filter(group=>group.items.length);
}
export function categoryLabel(item:Unknown,lang:'bn'|'en'){return labels[lang][item.category||'general']}
export function uncertaintyCategories(items:Unknown[],lang:'bn'|'en'){
 const categories=new Map<Category,Unknown[]>();
 for(const item of items){const category=item.category||'general';const rows=categories.get(category)||[];rows.push(item);categories.set(category,rows)}
 return Array.from(categories,([category,rows])=>({category,title:labels[lang][category],items:rows}));
}
export function emptySection(state:SectionState|undefined,lang:'bn'|'en'){
 return state==='not_stated'?(lang==='bn'?'উৎসে উল্লেখ নেই।':'Not stated in the source.'):(lang==='bn'?'এই অংশটি নিশ্চিত করা যায়নি। নিচে যা জানা যায়নি, তা দেখুন।':'We could not confirm this section. See what remains unclear below.');
}
export function partialSection(lang:'bn'|'en'){return lang==='bn'?'এই অংশের কিছু তথ্য নিশ্চিত করা যায়নি। নিচের সীমাবদ্ধতাগুলো দেখুন।':'Some information in this section could not be confirmed. Read the limitations below.'}

export function conditionLabel(lang:'bn'|'en'){return lang==='bn'?'এই তথ্যের প্রযোজ্য শর্ত · মূল উৎসের ভাষায়':'Conditions for this item · original source wording'}
export function standaloneClaimText(claim:{text:string;source_conditions?:string[]},lang:'bn'|'en'){
 return claim.text+(claim.source_conditions?.length?'\n'+conditionLabel(lang)+'\n'+claim.source_conditions.map(c=>'“'+c+'”').join('\n'):'');
}

export function completionLabel(done:number,total:number,lang:'bn'|'en'){
 const number=(value:number)=>value.toLocaleString(lang==='bn'?'bn-BD':'en');
 return lang==='bn'?`${number(total)}টির মধ্যে ${number(done)}টি সম্পন্ন`:`${number(done)}/${number(total)} completed`;
}

// Display original coverage passages without promoting them to admitted guidance.
export function presentUnknowns(items:Unknown[],evidence:{id:string;excerpt:string}[],_lang:'bn'|'en'){
 const generic=new Set(['This source passage could not be fully represented in the plan; check the original wording.','উৎসের এই অংশটি পরিকল্পনায় পুরোপুরি রাখা যায়নি; মূল লেখাটি দেখে নিন।']);
 const seen=new Set<string>();
 return items.flatMap(item=>{
  const quotes=evidence.filter(e=>item.evidence_ids.includes(e.id)).map(e=>e.excerpt);
  const text=generic.has(item.text)&&quotes.length?quotes.join('\n\n'):item.text;
  const key=JSON.stringify([item.kind,item.category,item.reason_code,text]);
  if(seen.has(key))return [];seen.add(key);
  return [{...item,text}];
 });
}

export function hasAdditionalSourcePassages(items:Unknown[],evidence:{id:string;excerpt:string}[]){
 return items.some(item=>(item.text==='This source passage could not be fully represented in the plan; check the original wording.'||item.text==='উৎসের এই অংশটি পরিকল্পনায় পুরোপুরি রাখা যায়নি; মূল লেখাটি দেখে নিন।')&&evidence.some(e=>item.evidence_ids.includes(e.id)));
}
