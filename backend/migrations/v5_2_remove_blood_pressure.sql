-- v5.2 Migration: Remove blood_pressure column from vitals table
-- This column is no longer needed as the hardware only measures HR, SpO2, and Temperature.

ALTER TABLE vitals DROP COLUMN IF EXISTS blood_pressure;
