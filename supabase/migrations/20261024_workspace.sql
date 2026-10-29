-- Apply only to the independent Gochalo Supabase project, after Clerk integration.
create table public.retrievals (
 id uuid primary key,
 user_id text not null default auth.jwt()->>'sub',
 data jsonb not null,
 revision bigint not null default 1,
 deleted boolean not null default false,
 updated_at timestamptz not null default now(),
 unique(id,user_id),
 check (octet_length(data::text) <= 524288)
);
create table public.tasks (
 id uuid primary key,
 user_id text not null default auth.jwt()->>'sub',
 retrieval_id uuid not null,
 data jsonb not null,
 revision bigint not null default 1,
 deleted boolean not null default false,
 updated_at timestamptz not null default now(),
 foreign key(retrieval_id,user_id) references public.retrievals(id,user_id),
 check (octet_length(data::text) <= 16384)
);
alter table public.retrievals enable row level security;
alter table public.tasks enable row level security;
create policy own_retrievals on public.retrievals for all to authenticated
 using (user_id=auth.jwt()->>'sub') with check(user_id=auth.jwt()->>'sub');
create policy own_tasks on public.tasks for all to authenticated
 using (user_id=auth.jwt()->>'sub') with check(user_id=auth.jwt()->>'sub');
-- Direct writes are prohibited: only the revision-checked function mutates rows.
revoke all on public.retrievals, public.tasks from anon, authenticated;
grant select on public.retrievals, public.tasks to authenticated;

create function public.apply_workspace_change(table_name text,record_id uuid,base_revision bigint,changes jsonb)
returns jsonb language plpgsql security definer set search_path=public,pg_temp as $$
declare
 actor text := auth.jwt()->>'sub';
 row_data jsonb;
 row_revision bigint;
 row_deleted boolean;
 row_time timestamptz;
 parent_id uuid;
 merged jsonb;
begin
 if actor is null or actor='' or table_name is null or table_name not in ('retrievals','tasks')
    or base_revision is null or base_revision<0
    or jsonb_typeof(changes) is distinct from 'object' or octet_length(changes::text)>524288 then
  raise exception 'invalid_workspace_change';
 end if;
 -- Serialize creation and updates of an ID; ownership never comes from the client.
 perform pg_advisory_xact_lock(hashtextextended(table_name||record_id::text,0));
 if table_name='retrievals' then
  select data,revision,deleted,updated_at into row_data,row_revision,row_deleted,row_time
   from public.retrievals where id=record_id and user_id=actor for update;
 else
  select data,revision,deleted,updated_at into row_data,row_revision,row_deleted,row_time
   from public.tasks where id=record_id and user_id=actor for update;
 end if;
 -- UUID-preserving imports and a lost creation response must not overwrite newer edits.
 if row_revision is not null and base_revision=0 and changes ? 'id' then
  return jsonb_build_object('conflict',false,'data',row_data,'revision',row_revision,'deleted',row_deleted,'updated_at',row_time);
 end if;
 if row_revision is not null and (row_deleted or row_revision<>base_revision) then
  return jsonb_build_object('conflict',not row_deleted,'data',row_data,'revision',row_revision,'deleted',row_deleted,'updated_at',row_time);
 end if;
 if row_revision is null and base_revision<>0 then raise exception 'missing_record'; end if;
 merged:=coalesce(row_data,'{}'::jsonb)||changes||jsonb_build_object('id',record_id,'schemaVersion',1);
 row_deleted:=coalesce((merged->>'deleted')::boolean,false);
 if table_name='retrievals' then
  if not row_deleted and (not (merged ?& array['title','kind','language','result','input','createdAt'])
     or length(merged->>'title') not between 1 and 160
     or coalesce(merged->>'kind','') not in ('research','ask','image','link','text')
     or coalesce(merged->>'language','') not in ('bn','en')
     or jsonb_typeof(merged->'result') is distinct from 'object') then
   raise exception 'invalid_retrieval';
  end if;
  if row_deleted then merged:=jsonb_build_object('id',record_id,'schemaVersion',1,'deleted',true); end if;
  insert into public.retrievals(id,user_id,data,revision,deleted)
   values(record_id,actor,merged,1,row_deleted)
   on conflict(id) do update set data=excluded.data,revision=public.retrievals.revision+1,
     deleted=excluded.deleted,updated_at=now() where public.retrievals.user_id=actor
   returning data,revision,deleted,updated_at into row_data,row_revision,row_deleted,row_time;
  if not found then raise exception 'record_unavailable'; end if;
  if row_deleted then
   update public.tasks set deleted=true,revision=revision+1,updated_at=now(),
    data=jsonb_build_object('id',id,'schemaVersion',1,'retrievalId',record_id,'deleted',true)
    where retrieval_id=record_id and user_id=actor and not deleted;
  end if;
 else
  parent_id:=(merged->>'retrievalId')::uuid;
  if row_data is not null and row_data->>'retrievalId'<>parent_id::text then raise exception 'immutable_parent'; end if;
  perform 1 from public.retrievals where id=parent_id and user_id=actor and not deleted for share;
  if not found then
   -- Parent deletion defeats stale offline task updates.
   if exists(select 1 from public.retrievals where id=parent_id and user_id=actor and deleted) then
    return jsonb_build_object('conflict',false,'data',jsonb_build_object('id',record_id,'retrievalId',parent_id,'deleted',true),
      'revision',coalesce(row_revision,0),'deleted',true,'updated_at',now());
   end if;
   raise exception 'parent_unavailable';
  end if;
  if not row_deleted and (not (merged ?& array['title','completed','saved','createdAt'])
    or length(merged->>'title') not between 1 and 2000
    or jsonb_typeof(merged->'completed') is distinct from 'boolean'
    or jsonb_typeof(merged->'saved') is distinct from 'boolean') then
   raise exception 'invalid_task';
  end if;
  if row_deleted then merged:=jsonb_build_object('id',record_id,'retrievalId',parent_id,'schemaVersion',1,'deleted',true); end if;
  insert into public.tasks(id,user_id,retrieval_id,data,revision,deleted)
   values(record_id,actor,parent_id,merged,1,row_deleted)
   on conflict(id) do update set data=excluded.data,revision=public.tasks.revision+1,
    deleted=excluded.deleted,updated_at=now() where public.tasks.user_id=actor
   returning data,revision,deleted,updated_at into row_data,row_revision,row_deleted,row_time;
  if not found then raise exception 'record_unavailable'; end if;
 end if;
 return jsonb_build_object('conflict',false,'data',row_data,'revision',row_revision,'deleted',row_deleted,'updated_at',row_time);
end $$;
revoke all on function public.apply_workspace_change(text,uuid,bigint,jsonb) from public,anon;
grant execute on function public.apply_workspace_change(text,uuid,bigint,jsonb) to authenticated;
