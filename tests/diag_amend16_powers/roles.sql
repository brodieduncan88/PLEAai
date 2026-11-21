\pset format unaligned
\pset fieldsep ' | '
\echo == 1. roles (cluster-wide)
select rolname, rolsuper as super, rolcreatedb as createdb, rolcreaterole as createrole, rolinherit as inherit, rolcanlogin as login, rolconnlimit as connlimit, rolbypassrls as bypassrls
  from pg_roles where rolname like 'plea%' or rolname = 'postgres' order by 1;
\echo == 2. role memberships
select r.rolname as role, m.rolname as member from pg_auth_members a join pg_roles r on r.oid = a.roleid join pg_roles m on m.oid = a.member where r.rolname like 'plea%' or m.rolname like 'plea%';
\echo == 3. server settings
select name, setting from pg_settings where name in ('max_connections', 'superuser_reserved_connections', 'password_encryption', 'statement_timeout', 'lock_timeout', 'idle_in_transaction_session_timeout');
\echo == 4. database and schema privileges (plea18, schema public)
select r.rolname, has_database_privilege(r.rolname, current_database(), 'CONNECT') as db_connect, has_database_privilege(r.rolname, current_database(), 'CREATE') as db_create,
       has_database_privilege(r.rolname, current_database(), 'TEMP') as db_temp, has_schema_privilege(r.rolname, 'public', 'USAGE') as schema_usage, has_schema_privilege(r.rolname, 'public', 'CREATE') as schema_create
  from pg_roles r where r.rolname like 'plea%' order by 1;
\echo == 5. tables: owner, and the privileges of each role
select c.relname as table, pg_get_userbyid(c.relowner) as owner, r.rolname as role,
       concat_ws(',', case when has_table_privilege(r.rolname, c.oid, 'SELECT') then 'SELECT' end, case when has_table_privilege(r.rolname, c.oid, 'INSERT') then 'INSERT' end,
                      case when has_table_privilege(r.rolname, c.oid, 'UPDATE') then 'UPDATE' end, case when has_table_privilege(r.rolname, c.oid, 'DELETE') then 'DELETE' end,
                      case when has_table_privilege(r.rolname, c.oid, 'TRUNCATE') then 'TRUNCATE' end, case when has_table_privilege(r.rolname, c.oid, 'REFERENCES') then 'REFERENCES' end,
                      case when has_table_privilege(r.rolname, c.oid, 'TRIGGER') then 'TRIGGER' end) as privileges
  from pg_class c join pg_namespace n on n.oid = c.relnamespace, pg_roles r
 where n.nspname = 'public' and c.relkind = 'r' and r.rolname in ('plea_local', 'plea_witness', 'plea_control') order by 1, 3;
\echo == 6. functions in public: owner, security definer, and who may execute
select p.proname as function, pg_get_userbyid(p.proowner) as owner, p.prosecdef as security_definer,
       has_function_privilege('plea_local', p.oid, 'EXECUTE') as plea_local, has_function_privilege('plea_witness', p.oid, 'EXECUTE') as plea_witness,
       has_function_privilege('plea_control', p.oid, 'EXECUTE') as plea_control, has_function_privilege('public', p.oid, 'EXECUTE') as public
  from pg_proc p join pg_namespace n on n.oid = p.pronamespace where n.nspname = 'public' order by 1;
\echo == 7. triggers on public tables
select c.relname as table, t.tgname as trigger, p.proname as function from pg_trigger t join pg_class c on c.oid = t.tgrelid join pg_proc p on p.oid = t.tgfoid join pg_namespace n on n.oid = c.relnamespace where n.nspname = 'public' and not t.tgisinternal order by 1, 2;
\echo == 8. row security
select relname, relrowsecurity, relforcerowsecurity from pg_class c join pg_namespace n on n.oid = c.relnamespace where n.nspname = 'public' and c.relkind = 'r' order by 1;
