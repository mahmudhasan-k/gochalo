import {afterEach,expect,it,vi} from 'vitest';
import {requestJson,REQUEST_TIMEOUT_MS} from './api';
afterEach(()=>{vi.useRealTimers();vi.unstubAllGlobals()});
it.each(['headers','body'])('bounds a stalled response %s without retrying',async(stage)=>{
 vi.useFakeTimers();
 const transport=vi.fn((_url:string,options:RequestInit)=>{
  const stalled=new Promise<never>((_resolve,reject)=>options.signal!.addEventListener('abort',()=>reject(new DOMException('Aborted','AbortError'))));
  return stage==='headers'?stalled:Promise.resolve({ok:true,json:()=>stalled});
 });
 vi.stubGlobal('fetch',transport);
 const request=requestJson('/api/jobs/existing','fictional-token');
 const rejected=expect(request).rejects.toThrow('timeout');
 await vi.advanceTimersByTimeAsync(REQUEST_TIMEOUT_MS);
 await rejected;
 expect(transport).toHaveBeenCalledTimes(1);
 expect(vi.getTimerCount()).toBe(0);
});
it('clears the deadline after a successful response',async()=>{
 vi.useFakeTimers();
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({status:'done'}))));
 await expect(requestJson('/api/jobs/existing','fictional-token')).resolves.toEqual({status:'done'});
 expect(vi.getTimerCount()).toBe(0);
});
