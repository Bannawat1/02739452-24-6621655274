#!/bin/bash
# รันอัตโนมัติครั้งแรกที่สร้าง container postgres: สร้างผู้ใช้/ฐานข้อมูล traffic จากค่าใน .env แล้วสร้างตาราง
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<EOSQL
CREATE USER "$TRAFFIC_DB_USER" WITH PASSWORD '$TRAFFIC_DB_PASSWORD';
CREATE DATABASE traffic OWNER "$TRAFFIC_DB_USER";
EOSQL
psql -v ON_ERROR_STOP=1 --username "$TRAFFIC_DB_USER" --dbname traffic -f /sql/schema.sql
