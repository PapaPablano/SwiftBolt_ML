-- Storage Buckets Configuration
-- Creates buckets for ML artifacts, chart exports, and reports with proper RLS policies

-- =============================================================================
-- 1. CREATE STORAGE BUCKETS
-- =============================================================================

-- ml-artifacts: Store trained ML models, feature scalers, and model metadata
-- Access: service_role only (automated ML pipeline)
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'ml-artifacts',
    'ml-artifacts',
    false,  -- Private bucket
    52428800,  -- 50MB limit per file
    ARRAY['application/octet-stream', 'application/json', 'application/x-pickle']
) ON CONFLICT (id) DO NOTHING;

-- charts: Store exported chart images for sharing/embedding
-- Access: authenticated users can read, service_role can write
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'charts',
    'charts',
    true,  -- Public bucket for embedding
    5242880,  -- 5MB limit per file
    ARRAY['image/png', 'image/jpeg', 'image/svg+xml', 'image/webp']
) ON CONFLICT (id) DO NOTHING;

-- reports: Store generated PDF/CSV reports
-- Access: authenticated users can read their own, service_role can manage all
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'reports',
    'reports',
    false,  -- Private bucket
    10485760,  -- 10MB limit per file
    ARRAY['application/pdf', 'text/csv', 'application/json']
) ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- 2. RLS POLICIES FOR storage.objects
-- =============================================================================

-- Note: RLS on storage.objects uses path conventions for access control
-- Path format: bucket_id/user_id/filename or bucket_id/public/filename

-- -----------------------------------------------------------------------------
-- ml-artifacts: Service role only
-- -----------------------------------------------------------------------------
CREATE POLICY "ml_artifacts_service_role_all"
ON storage.objects FOR ALL
TO service_role
USING (bucket_id = 'ml-artifacts')
WITH CHECK (bucket_id = 'ml-artifacts');

-- -----------------------------------------------------------------------------
-- charts: Public read, service_role write
-- -----------------------------------------------------------------------------

-- Anyone can read public charts
CREATE POLICY "charts_public_read"
ON storage.objects FOR SELECT
TO anon, authenticated
USING (bucket_id = 'charts');

-- Service role can manage all charts
CREATE POLICY "charts_service_role_all"
ON storage.objects FOR ALL
TO service_role
USING (bucket_id = 'charts')
WITH CHECK (bucket_id = 'charts');

-- Authenticated users can upload their own charts (path: charts/user_id/*)
CREATE POLICY "charts_authenticated_insert"
ON storage.objects FOR INSERT
TO authenticated
WITH CHECK (
    bucket_id = 'charts'
    AND (storage.foldername(name))[1] = auth.uid()::text
);

-- Authenticated users can delete their own charts
CREATE POLICY "charts_authenticated_delete"
ON storage.objects FOR DELETE
TO authenticated
USING (
    bucket_id = 'charts'
    AND (storage.foldername(name))[1] = auth.uid()::text
);

-- -----------------------------------------------------------------------------
-- reports: User-specific access
-- -----------------------------------------------------------------------------

-- Users can read their own reports (path: reports/user_id/*)
CREATE POLICY "reports_user_read"
ON storage.objects FOR SELECT
TO authenticated
USING (
    bucket_id = 'reports'
    AND (storage.foldername(name))[1] = auth.uid()::text
);

-- Service role can manage all reports
CREATE POLICY "reports_service_role_all"
ON storage.objects FOR ALL
TO service_role
USING (bucket_id = 'reports')
WITH CHECK (bucket_id = 'reports');

-- =============================================================================
-- 3. HELPER FUNCTIONS FOR STORAGE PATHS
-- =============================================================================

-- Generate a unique storage path for user files
CREATE OR REPLACE FUNCTION generate_user_storage_path(
    p_bucket TEXT,
    p_user_id UUID,
    p_filename TEXT
)
RETURNS TEXT
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN format('%s/%s/%s_%s',
        p_bucket,
        p_user_id::text,
        to_char(now(), 'YYYYMMDD_HH24MISS'),
        p_filename
    );
END;
$$;

-- Generate a public storage path (no user association)
CREATE OR REPLACE FUNCTION generate_public_storage_path(
    p_bucket TEXT,
    p_filename TEXT
)
RETURNS TEXT
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN format('%s/public/%s_%s',
        p_bucket,
        to_char(now(), 'YYYYMMDD_HH24MISS'),
        p_filename
    );
END;
$$;

-- Grant execute to authenticated users
GRANT EXECUTE ON FUNCTION generate_user_storage_path TO authenticated;
GRANT EXECUTE ON FUNCTION generate_public_storage_path TO authenticated, service_role;

-- =============================================================================
-- 4. CLEANUP POLICY (optional - uncomment if needed)
-- =============================================================================

-- Automatic cleanup of old files can be implemented via:
-- 1. pg_cron job that deletes files older than X days
-- 2. Edge Function triggered on schedule
--
-- Example cleanup function (uncomment to enable):
--
-- CREATE OR REPLACE FUNCTION cleanup_old_storage_files(
--     p_bucket TEXT,
--     p_days_old INTEGER DEFAULT 30
-- )
-- RETURNS INTEGER
-- LANGUAGE plpgsql
-- SECURITY DEFINER
-- AS $$
-- DECLARE
--     deleted_count INTEGER := 0;
-- BEGIN
--     DELETE FROM storage.objects
--     WHERE bucket_id = p_bucket
--       AND created_at < now() - (p_days_old || ' days')::interval;
--
--     GET DIAGNOSTICS deleted_count = ROW_COUNT;
--     RETURN deleted_count;
-- END;
-- $$;
