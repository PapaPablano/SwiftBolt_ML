-- Check what version of the function is actually in the database
SELECT 
    proname as function_name,
    pg_get_functiondef(oid) as function_definition
FROM pg_proc 
WHERE proname = 'get_chart_data_v2_dynamic';
