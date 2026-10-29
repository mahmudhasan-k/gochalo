import {expect,it} from 'vitest';
import {mergeCacheDelta} from './cacheMerge';
import {emptyData,type Operation} from './productTypes';
const op=(id:string):Operation=>({id,table:'tasks',recordId:'task',baseRevision:1,createdAt:'2026-10-25',patch:{completed:true}});
it('does not resurrect an operation acknowledged by another tab',()=>{
 const before={...emptyData(),outbox:[op('acknowledged')]};
 expect(mergeCacheDelta(emptyData(),before,structuredClone(before)).outbox).toEqual([]);
});
it('an acknowledgement removes only that operation, preserving concurrent queued edits',()=>{
 const before={...emptyData(),outbox:[op('old')]},latest={...emptyData(),outbox:[op('old'),op('other-tab')]};
 expect(mergeCacheDelta(latest,before,emptyData()).outbox.map(op=>op.id)).toEqual(['other-tab']);
});
