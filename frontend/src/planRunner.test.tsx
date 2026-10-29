import {webcrypto} from 'node:crypto';
import {act,cleanup,renderHook} from '@testing-library/react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {usePlanRunner} from './usePlanRunner';
import examples from '../public/examples.json';
const result={...structuredClone(examples['en-general'].result),demo:false,review_mode:'ai_reviewed'};
const json=(value:unknown,status=200)=>new Response(JSON.stringify(value),{status});
beforeEach(()=>vi.stubGlobal('crypto',webcrypto));
afterEach(()=>{cleanup();vi.unstubAllGlobals()});
it('automatically chains extraction and checked analysis without claiming human confirmation',async()=>{
 const paths:string[]=[],bodies:any[]=[];
 vi.stubGlobal('fetch',vi.fn(async(path:string,options:any)=>{paths.push(path);if(path.endsWith('/session'))return json({token:'offline'});if(path==='/api/extract/link')return json({job_id:'extraction'},202);if(path.endsWith('/jobs/extraction'))return json({status:'succeeded',result:{text:'Source text',requested_url:'https://example.org',returned_url:'https://example.org/page',retrieved_at:'2026-10-24T00:00:00Z'}});if(path==='/api/analysis'){bodies.push(JSON.parse(options.body));return json({job_id:'analysis'},202)}if(path.endsWith('/jobs/analysis'))return json({status:'succeeded',result});throw new Error(path)}));
 const hook=renderHook(()=>usePlanRunner());let retrieved:any;
 await act(async()=>{retrieved=await hook.result.current.run({kind:'link',url:'https://example.org',text:'',context:'',language:'en',file:null})});
 expect(paths.filter(path=>path==='/api/extract/link')).toHaveLength(1);expect(paths.filter(path=>path==='/api/analysis')).toHaveLength(1);
 expect(bodies[0]).toMatchObject({text:'Source text',kind:'link',reviewed:false});
 expect(retrieved).toMatchObject({input:'Source text',sourceUrl:'https://example.org',returnedUrl:'https://example.org/page'});
 expect(retrieved).not.toHaveProperty('file');expect(hook.result.current.pending).toBe(false);
});
it('reuses extracted text after an analysis failure',async()=>{
 let extractionCalls=0,analysisCalls=0;
 vi.stubGlobal('fetch',vi.fn(async(path:string)=>{if(path.endsWith('/session'))return json({token:'offline'});if(path.endsWith('/extract/link')){extractionCalls++;return json({job_id:'extracted'},202)}if(path.endsWith('/jobs/extracted'))return json({status:'succeeded',result:{text:'Retained source'}});if(path.endsWith('/analysis')){analysisCalls++;return json({job_id:'analysis'+analysisCalls},202)}if(path.endsWith('/jobs/analysis1'))return json({status:'failed',error:'review_failed'});if(path.endsWith('/jobs/analysis2'))return json({status:'succeeded',result});throw new Error(path)}));
 const hook=renderHook(()=>usePlanRunner());await act(async()=>{expect(await hook.result.current.run({kind:'link',url:'https://example.org',text:'',context:'',language:'en',file:null})).toBeNull()});
 expect(hook.result.current.prepared.text).toBe('Retained source');
 await act(async()=>{expect(await hook.result.current.run()).not.toBeNull()});
 expect(extractionCalls).toBe(1);expect(analysisCalls).toBe(2);
});
it('resumes an uncertain research POST by lookup without resubmission or Quick Plan fallback',async()=>{
 let submissions=0,lookups=0;
 vi.stubGlobal('fetch',vi.fn(async(path:string)=>{if(path.endsWith('/session'))return json({token:'offline'});if(path==='/api/research'){submissions++;throw new TypeError('lost response')}if(path.includes('/api/requests/')){lookups++;return json({job_id:'research'})}if(path.endsWith('/jobs/research'))return json({status:'succeeded',result:{...result,review_mode:'web_research'}});throw new Error(path)}));
 const hook=renderHook(()=>usePlanRunner());await act(async()=>{expect(await hook.result.current.run({kind:'research',url:'',text:'Goal',context:'Home',language:'en',file:null})).toBeNull()});
 expect(hook.result.current.pending).toBe(true);let restored:any;
 await act(async()=>{restored=await hook.result.current.run()});
 expect(submissions).toBe(1);expect(lookups).toBe(1);expect(restored.result.review_mode).toBe('web_research');
});

it('keeps ordinary questions on General Ask and never discovers web sources',async()=>{
 const bodies:any[]=[];const paths:string[]=[];
 vi.stubGlobal('fetch',vi.fn(async(path:string,options:any)=>{paths.push(path);if(path.endsWith('/session'))return json({token:'offline'});if(path==='/api/analysis'){bodies.push(JSON.parse(options.body));return json({job_id:'ask'},202)}if(path.endsWith('/jobs/ask'))return json({status:'succeeded',result:{...result,review_mode:'general_ask',semantic_review_complete:false,evidence:[]}});throw new Error(path)}));
 const hook=renderHook(()=>usePlanRunner());let row:any;
 await act(async()=>{row=await hook.result.current.run({kind:'ask',url:'',text:'Organize my study week.',context:'',language:'en',file:null})});
 expect(bodies).toHaveLength(1);expect(bodies[0].kind).toBe('ask');expect(paths).not.toContain('/api/research');expect(row.result.review_mode).toBe('general_ask');
});

it('uses the owned extraction reference for a large unedited source and retains full saved text',async()=>{
 const text='ক'.repeat(49000),bodies:any[]=[];
 vi.stubGlobal('fetch',vi.fn(async(path:string,options:any)=>{if(path.endsWith('/session'))return json({token:'offline'});if(path==='/api/extract/link')return json({job_id:'large-source'},202);if(path.endsWith('/jobs/large-source'))return json({status:'succeeded',result:{text}});if(path==='/api/analysis'){bodies.push(JSON.parse(options.body));return json({job_id:'plan'},202)}if(path.endsWith('/jobs/plan'))return json({status:'succeeded',result});throw new Error(path)}));
 const hook=renderHook(()=>usePlanRunner());let row:any;
 await act(async()=>{row=await hook.result.current.run({kind:'link',url:'https://example.org',text:'',context:'',language:'bn',file:null})});
 expect(bodies[0].extraction_job_id).toBe('large-source');expect(bodies[0]).not.toHaveProperty('text');expect(row.input).toBe(text);expect(row.extractedOriginal).toBe(text);expect(row).not.toHaveProperty('extractionJobId');
});
