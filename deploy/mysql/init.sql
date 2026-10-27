-- MySQL initialization script for video-cut
-- This script runs automatically when the MySQL container is first created

-- Create database if not exists (redundant with env vars, but ensures it exists)
CREATE DATABASE IF NOT EXISTS `video_cut`
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

-- Grant privileges to application user
GRANT ALL PRIVILEGES ON `video_cut`.* TO 'videocut'@'%';
FLUSH PRIVILEGES;

-- Set timezone
SET GLOBAL time_zone = '+8:00';
