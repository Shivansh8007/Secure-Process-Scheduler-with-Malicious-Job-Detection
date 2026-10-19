-- ====================================================================
-- JobSentinel Database Schema (MySQL 8.0)
-- Process Scheduler with Persistent Database Queue
-- Phase 2: MySQL, Backend, Job Lifecycle, Scheduler & Worker Interfaces
-- ====================================================================

CREATE DATABASE IF NOT EXISTS jobsentinel
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE jobsentinel;

-- --------------------------------------------------------------------
-- Table 1: jobs
-- Stores submitted jobs, arrival timing, CPU characteristics, and status
-- --------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jobs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    job_id VARCHAR(64) NOT NULL UNIQUE,
    command TEXT NOT NULL,
    arrival_time DOUBLE NOT NULL COMMENT 'Arrival timestamp or simulation time unit',
    burst_time DOUBLE NOT NULL COMMENT 'Expected CPU burst time required for execution',
    priority INT NOT NULL DEFAULT 1 COMMENT 'Lower or higher value depending on scheduler priority scheme',
    status ENUM('PENDING', 'SCHEDULED', 'RUNNING', 'COMPLETED', 'FAILED', 'QUARANTINED') NOT NULL DEFAULT 'PENDING',
    algorithm VARCHAR(32) NULL COMMENT 'Algorithm that scheduled the job (FCFS, SJF, ROUND_ROBIN, PRIORITY)',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME NULL,
    completed_at DATETIME NULL,
    INDEX idx_jobs_status (status),
    INDEX idx_jobs_arrival_time (arrival_time),
    INDEX idx_jobs_priority (priority),
    INDEX idx_jobs_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------------------
-- Table 2: execution_history
-- Preserves execution records, worker assignment, outputs, and metrics
-- --------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS execution_history (
    history_id INT AUTO_INCREMENT PRIMARY KEY,
    job_id VARCHAR(64) NOT NULL,
    worker_id VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL,
    output LONGTEXT NULL,
    error_message LONGTEXT NULL,
    started_at DATETIME NULL,
    completed_at DATETIME NULL,
    execution_time DOUBLE NULL COMMENT 'Actual wall-clock execution time in seconds',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE,
    INDEX idx_history_job_id (job_id),
    INDEX idx_history_worker_id (worker_id),
    INDEX idx_history_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------------------
-- Table 3: audit_logs
-- Immutable audit log of job lifecycle events for traceability
-- --------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_logs (
    audit_id INT AUTO_INCREMENT PRIMARY KEY,
    job_id VARCHAR(64) NOT NULL,
    event_type VARCHAR(64) NOT NULL COMMENT 'e.g. JOB_CREATED, JOB_SCHEDULED, JOB_STARTED, JOB_COMPLETED, JOB_FAILED',
    message VARCHAR(500) NOT NULL,
    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE,
    INDEX idx_audit_job_id (job_id),
    INDEX idx_audit_event_type (event_type),
    INDEX idx_audit_timestamp (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
