import {describe,it,expect} from 'vitest';
import {COPY} from './uiCopy';
import {hasAdditionalSourcePassages,presentUnknowns,uncertaintyGroups,uncertaintyCategories,emptySection,categoryLabel,partialSection,standaloneClaimText,type Unknown} from './resultPresentation';
describe('uncertainty presentation',()=>{
 it('groups missing, conflicts and unconfirmed details with stable category order',()=>{
  const items:Unknown[]=[{kind:'unverified',category:'steps',text:'Step scope',evidence_ids:[]},{kind:'missing',category:'fees',text:'Fee A',evidence_ids:[]},{kind:'contradiction',category:'eligibility',text:'Conflict',evidence_ids:['e1','e2']},{kind:'missing',category:'documents',text:'Documents',evidence_ids:[]},{kind:'missing',category:'fees',text:'Fee B',evidence_ids:[]}];
  const before=JSON.stringify(items);const groups=uncertaintyGroups(items,'en');
  expect(groups.map(g=>g.kind)).toEqual(['missing','contradiction','unverified']);
  expect(groups[0].items.map(u=>u.text)).toEqual(['Documents','Fee A','Fee B']);
  expect(JSON.stringify(items)).toBe(before);
 });
 it('treats legacy empty sections as unconfirmed',()=>{
  for(const lang of ['bn','en'] as const){expect(emptySection(undefined,lang)).toBe(emptySection('unconfirmed',lang));expect(emptySection('not_stated',lang)).not.toBe(emptySection(undefined,lang));expect(partialSection(lang)).toBeTruthy()}
 });
 it('authors category and group labels in both interface languages while preserving content',()=>{
  const item:Unknown={kind:'unverified',category:'fees',text:'Original generated wording',evidence_ids:['e1']};
  expect(categoryLabel(item,'bn')).toBe(COPY.bn.fees);expect(categoryLabel(item,'en')).toBe(COPY.en.fees);
  expect(uncertaintyGroups([item],'bn')[0].items[0]).toBe(item);
 });
 it('places older uncategorized unknowns under other information',()=>{
  expect(categoryLabel({kind:'missing',text:'Legacy',evidence_ids:[]},'en')).toBe('Other information');
 });
 it('keeps each status separate while grouping topic rows and retaining legacy content and evidence',()=>{
  const items:Unknown[]=[{kind:'missing',category:'fees',text:'Missing fee',evidence_ids:['e1']},{kind:'unverified',category:'fees',text:'Unconfirmed exemption',evidence_ids:['e2']},{kind:'unverified',category:'fees',text:'Unconfirmed payment method',evidence_ids:[]},{kind:'unverified',text:'Legacy point',evidence_ids:[]}];
  const before=JSON.stringify(items);
  const groups=uncertaintyGroups(items,'en').map(group=>({kind:group.kind,categories:uncertaintyCategories(group.items,'en')}));
  expect(groups.map(group=>group.kind)).toEqual(['missing','unverified']);
  expect(groups[0].categories[0].items).toEqual([items[0]]);
  expect(groups[1].categories.map(category=>category.category)).toEqual(['fees','general']);
  expect(groups[1].categories[0].items).toEqual([items[1],items[2]]);
  expect(groups[1].categories[0].items[0]).toBe(items[1]);
  expect(groups[1].categories[1].title).toBe('Other information');
  expect(uncertaintyCategories([items[1]],'bn')[0].title).toBe(COPY.bn.fees);
  expect(JSON.stringify(items)).toBe(before);
 });
});

it('retains exact attached source conditions in the standalone copy text',()=>{
 const quote='Only current students who live in this district may apply.';
 expect(standaloneClaimText({text:'Submit the form.',source_conditions:[quote]},'en')).toContain(quote);
 expect(standaloneClaimText({text:'Submit the form.'},'en')).toBe('Submit the form.');
});

it('shows exact coverage passages, preserves distinct exceptions and does not mutate saved metadata',()=>{
 const text='This source passage could not be fully represented in the plan; check the original wording.';
 const base:Unknown={kind:'unverified',category:'steps',reason_code:'unsupported_interpretation',text,evidence_ids:['e1']};
 const items=[base,{...base},{...base,evidence_ids:['e2']}],before=JSON.stringify(items);
 const output=presentUnknowns(items,[{id:'e1',excerpt:'A video is optional.'},{id:'e2',excerpt:'If submitted, the video must be in English.'}],'en');
 expect(output.map(item=>item.text)).toEqual(['A video is optional.','If submitted, the video must be in English.']);
 expect(output.every(item=>item.kind==='unverified')).toBe(true);expect(JSON.stringify(items)).toBe(before);
 expect(presentUnknowns([base],[],'en')[0].text).toBe(text);
 expect(hasAdditionalSourcePassages([base],[])).toBe(false);
 expect(hasAdditionalSourcePassages([base],[{id:'e1',excerpt:'Original condition.'}])).toBe(true);
 expect(hasAdditionalSourcePassages([{...base,text:'The current fee is unknown.'}],[{id:'e1',excerpt:'Original condition.'}])).toBe(false);
});
