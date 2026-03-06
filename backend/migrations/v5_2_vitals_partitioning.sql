-- ═══════════════════════════════════════════════════════════════════════════════
--  v5.2 FIX 8: Vitals Table Partitioning by Month
--  Converts the vitals table to range-partitioned by timestamp.
--  This improves query performance and enables efficient retention cleanup.
--
--  WARNING: Run during maintenance window. This migrates all existing data.
--  Estimated time: ~1 min per 1M rows.
--
--  Usage:  psql -U postgres -d patient_monitor -f v5_2_vitals_partitioning.sql
-- ═══════════════════════════════════════════════════════════════════════════════

BEGIN;

-- Step 1: Rename original table
ALTER TABLE IF EXISTS vitals RENAME TO vitals_old;

-- Step 2: Drop indexes on old table (they'll be recreated on partitions)
DROP INDEX IF EXISTS idx_vitals_patient_ts;

-- Step 3: Create partitioned table with same schema
CREATE TABLE vitals (
    vital_id       SERIAL,
    patient_id     INTEGER NOT NULL REFERENCES patients(patient_id),
    heart_rate     INTEGER,
    spo2           INTEGER,
    temperature    DOUBLE PRECISION,
    "timestamp"    TIMESTAMP DEFAULT now(),
    PRIMARY KEY (vital_id, "timestamp")
) PARTITION BY RANGE ("timestamp");

-- Step 4: Create partitions for current month ± 3 months
-- Adjust dates as needed for your deployment window.
DO $$
DECLARE
    start_date DATE;
    end_date DATE;
    partition_name TEXT;
BEGIN
    -- Create partitions from 3 months ago to 3 months ahead
    FOR i IN -3..3 LOOP
        start_date := date_trunc('month', CURRENT_DATE + (i || ' months')::interval);
        end_date := start_date + '1 month'::interval;
        partition_name := 'vitals_' || to_char(start_date, 'YYYY_MM');

        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS %I PARTITION OF vitals FOR VALUES FROM (%L) TO (%L)',
            partition_name, start_date, end_date
        );

        -- Add index per partition for patient + timestamp queries
        EXECUTE format(
            'CREATE INDEX IF NOT EXISTS %I ON %I (patient_id, "timestamp" DESC)',
            'idx_' || partition_name || '_patient_ts', partition_name
        );
    END LOOP;
END $$;

-- Step 5: Create default partition for any out-of-range data
CREATE TABLE IF NOT EXISTS vitals_default PARTITION OF vitals DEFAULT;
CREATE INDEX IF NOT EXISTS idx_vitals_default_patient_ts
    ON vitals_default (patient_id, "timestamp" DESC);

-- Step 6: Migrate existing data
INSERT INTO vitals (vital_id, patient_id, heart_rate, spo2, temperature, "timestamp")
SELECT vital_id, patient_id, heart_rate, spo2, temperature, "timestamp"
FROM vitals_old;

-- Step 7: Update the sequence to continue from the last vital_id
SELECT setval('vitals_vital_id_seq', COALESCE((SELECT MAX(vital_id) FROM vitals), 1));

-- Step 8: Update foreign keys pointing to vitals
-- alerts.vital_id references vitals — need to drop & recreate
ALTER TABLE alerts DROP CONSTRAINT IF EXISTS alerts_vital_id_fkey;
ALTER TABLE alerts ADD CONSTRAINT alerts_vital_id_fkey
    FOREIGN KEY (vital_id) REFERENCES vitals(vital_id, "timestamp") NOT VALID;
-- Note: NOT VALID skips validation of existing rows (faster).
-- Run ALTER TABLE alerts VALIDATE CONSTRAINT alerts_vital_id_fkey; afterwards.

-- Step 9: Drop old table after successful migration
-- Uncomment after verifying the migration:
-- DROP TABLE IF EXISTS vitals_old;

COMMIT;

-- ═══════════════════════════════════════════════════════════════════════════════
--  Partition Maintenance: Run monthly to create next month's partition.
--  Add to cron or pg_cron:
--
--  SELECT create_monthly_vitals_partition();
-- ═══════════════════════════════════════════════════════════════════════════════
CREATE OR REPLACE FUNCTION create_monthly_vitals_partition()
RETURNS void AS $$
DECLARE
    next_month DATE := date_trunc('month', CURRENT_DATE + '1 month'::interval);
    end_month DATE := next_month + '1 month'::interval;
    partition_name TEXT := 'vitals_' || to_char(next_month, 'YYYY_MM');
BEGIN
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF vitals FOR VALUES FROM (%L) TO (%L)',
        partition_name, next_month, end_month
    );
    EXECUTE format(
        'CREATE INDEX IF NOT EXISTS %I ON %I (patient_id, "timestamp" DESC)',
        'idx_' || partition_name || '_patient_ts', partition_name
    );
    RAISE NOTICE 'Created partition: %', partition_name;
END;
$$ LANGUAGE plpgsql;
