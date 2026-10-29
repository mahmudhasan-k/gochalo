// @vitest-environment node
import {readFileSync} from 'node:fs';
import {PGlite} from '@electric-sql/pglite';
import {afterAll,beforeAll,expect,it} from 'vitest';
let db:PGlite;
const parent='10000000-0000-4000-8000-000000000001',child='20000000-0000-4000-8000-000000000001';
async function actor(id:string){await db.query("select set_config('request.jwt.claims', $1, false)",[JSON.stringify({sub:id,role:'authenticated'})])}
async function change(table:string,id:string,revision:number,patch:unknown){const result=await db.query<{value:any}>('select public.apply_workspace_change($1,$2,$3,$4::jsonb) as value',[table,id,revision,JSON.stringify(patch)]);return result.rows[0].value}
beforeAll(async()=>{
 db=new PGlite();await db.exec("create role anon; create role authenticated; create schema auth; create function auth.jwt() returns jsonb language sql stable as $$ select coalesce(nullif(current_setting('request.jwt.claims',true),''),'{}')::jsonb $$; grant usage on schema auth to authenticated;");
 await db.exec(readFileSync(new URL('../../supabase/migrations/20261024_workspace.sql',import.meta.url),'utf8'));
 await db.exec('set role authenticated');await actor('user_a');
},30000);
afterAll(async()=>{await db?.close()});
it('executes the migration and rejects malformed records without cloud access',async()=>{
 await expect(change('retrievals',parent,0,{})).rejects.toThrow('invalid_retrieval');
 await expect(change('not_a_table',parent,0,{})).rejects.toThrow('invalid_workspace_change');
});
it('isolates two owners and forbids direct writes',async()=>{
 const created=await change('retrievals',parent,0,{id:parent,title:'My plan',kind:'research',language:'en',input:'Goal',createdAt:'2026-10-24T00:00:00Z',result:{sections:{steps:[]}}});
 expect(created.revision).toBe(1);
 await expect(db.query("update public.retrievals set data='{}' where id=$1",[parent])).rejects.toThrow(/permission denied/);
 await actor('user_b');expect((await db.query('select * from public.retrievals')).rows).toEqual([]);
 await expect(change('retrievals',parent,0,{id:parent,title:'Steal',kind:'ask',language:'en',input:'Goal',createdAt:'now',result:{}})).rejects.toThrow('record_unavailable');
 expect((await db.query('select * from public.tasks')).rows).toEqual([]);await actor('user_a');
 expect((await db.query('select * from public.retrievals')).rows).toHaveLength(1);
});
it('preserves newer edits when an import is repeated after a lost response',async()=>{
 const update=await change('retrievals',parent,1,{title:'Renamed'});expect(update.revision).toBe(2);
 const repeated=await change('retrievals',parent,0,{id:parent,title:'Old import'});
 expect(repeated.data.title).toBe('Renamed');expect(repeated.revision).toBe(2);expect(repeated.conflict).toBe(false);
});
it('reports revision conflicts and replays field edits without losing unrelated changes',async()=>{
 const created=await change('tasks',child,0,{id:child,retrievalId:parent,title:'Task',completed:false,saved:true,createdAt:'now'});expect(created.revision).toBe(1);
 await change('tasks',child,1,{title:'Personal wording'});
 const conflict=await change('tasks',child,1,{completed:true});expect(conflict.conflict).toBe(true);expect(conflict.data.completed).toBe(false);
 const resolved=await change('tasks',child,conflict.revision,{completed:true});
 expect(resolved.data).toMatchObject({title:'Personal wording',completed:true});
 await actor('user_b');await expect(change('tasks','20000000-0000-4000-8000-000000000002',0,{retrievalId:parent,title:'Foreign task',completed:false,saved:true,createdAt:'now'})).rejects.toThrow('parent_unavailable');await actor('user_a');
});
it('deletes content and linked tasks and defeats stale offline resurrection',async()=>{
 const deleted=await change('retrievals',parent,2,{deleted:true});expect(deleted.deleted).toBe(true);expect(deleted.data.input).toBeUndefined();expect(deleted.data.result).toBeUndefined();
 const children=await db.query<{data:any;deleted:boolean}>('select data,deleted from public.tasks');expect(children.rows[0].deleted).toBe(true);expect(children.rows[0].data.title).toBeUndefined();
 const late=await change('tasks',child,3,{completed:false});expect(late.deleted).toBe(true);
 const resurrect=await change('retrievals',parent,0,{id:parent,title:'Return',deleted:false});expect(resurrect.deleted).toBe(true);
});
