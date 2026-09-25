-- RetailMind AI academic MySQL 8.4 schema. Run before indexes.sql and seed.sql.
CREATE DATABASE IF NOT EXISTS retailmind CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE retailmind;

CREATE TABLE IF NOT EXISTS categories (
  category_id VARCHAR(100) PRIMARY KEY,
  category_name VARCHAR(150) NOT NULL
);
CREATE TABLE IF NOT EXISTS regions (
  region_id VARCHAR(100) PRIMARY KEY,
  region_name VARCHAR(150) NOT NULL
);
CREATE TABLE IF NOT EXISTS suppliers (
  supplier_id VARCHAR(100) PRIMARY KEY,
  supplier_name VARCHAR(150) NOT NULL
);
CREATE TABLE IF NOT EXISTS products (
  product_id VARCHAR(64) PRIMARY KEY,
  product_name VARCHAR(255) NOT NULL,
  category_id VARCHAR(100) NOT NULL,
  supplier_id VARCHAR(100),
  FOREIGN KEY (category_id) REFERENCES categories(category_id),
  FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
);
CREATE TABLE IF NOT EXISTS stores (
  store_id VARCHAR(64) PRIMARY KEY,
  store_name VARCHAR(255) NOT NULL,
  region_id VARCHAR(100) NOT NULL,
  latitude DECIMAL(9,6),
  longitude DECIMAL(9,6),
  FOREIGN KEY (region_id) REFERENCES regions(region_id)
);
CREATE TABLE IF NOT EXISTS calendar (
  calendar_date DATE PRIMARY KEY,
  weekday_num TINYINT NOT NULL,
  month_num TINYINT NOT NULL,
  year_num SMALLINT NOT NULL,
  holiday BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE IF NOT EXISTS promotions (
  promotion_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  product_id VARCHAR(64) NOT NULL,
  store_id VARCHAR(64),
  start_date DATE NOT NULL,
  end_date DATE NOT NULL,
  discount_rate DECIMAL(7,4) NOT NULL DEFAULT 0,
  CHECK (discount_rate >= 0 AND discount_rate < 1),
  CHECK (end_date >= start_date),
  FOREIGN KEY (product_id) REFERENCES products(product_id),
  FOREIGN KEY (store_id) REFERENCES stores(store_id)
);
CREATE TABLE IF NOT EXISTS prices (
  product_id VARCHAR(64) NOT NULL,
  store_id VARCHAR(64) NOT NULL,
  effective_date DATE NOT NULL,
  unit_price DECIMAL(14,2) NOT NULL,
  CHECK (unit_price >= 0),
  PRIMARY KEY (product_id, store_id, effective_date),
  FOREIGN KEY (product_id) REFERENCES products(product_id),
  FOREIGN KEY (store_id) REFERENCES stores(store_id)
);
CREATE TABLE IF NOT EXISTS sales (
  sale_date DATE NOT NULL,
  product_id VARCHAR(64) NOT NULL,
  store_id VARCHAR(64) NOT NULL,
  units DECIMAL(14,2) NOT NULL,
  unit_price DECIMAL(14,2),
  returns_units DECIMAL(14,2) NOT NULL DEFAULT 0,
  promotion BOOLEAN NOT NULL DEFAULT FALSE,
  CHECK (units >= 0),
  CHECK (returns_units >= 0),
  PRIMARY KEY (sale_date, product_id, store_id),
  FOREIGN KEY (sale_date) REFERENCES calendar(calendar_date),
  FOREIGN KEY (product_id) REFERENCES products(product_id),
  FOREIGN KEY (store_id) REFERENCES stores(store_id)
);
CREATE TABLE IF NOT EXISTS inventory (
  snapshot_date DATE NOT NULL,
  product_id VARCHAR(64) NOT NULL,
  store_id VARCHAR(64) NOT NULL,
  on_hand DECIMAL(14,2),
  lead_time_days SMALLINT,
  CHECK (on_hand IS NULL OR on_hand >= 0),
  CHECK (lead_time_days IS NULL OR lead_time_days >= 0),
  PRIMARY KEY (snapshot_date, product_id, store_id),
  FOREIGN KEY (product_id) REFERENCES products(product_id),
  FOREIGN KEY (store_id) REFERENCES stores(store_id)
);
CREATE TABLE IF NOT EXISTS model_runs (
  run_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  model_name VARCHAR(100) NOT NULL,
  model_version VARCHAR(100) NOT NULL,
  trained_at DATETIME NOT NULL,
  dataset_checksum CHAR(64) NOT NULL,
  horizon_days SMALLINT NOT NULL,
  feature_config JSON,
  training_config JSON,
  UNIQUE KEY uq_model_run_version (model_version, dataset_checksum)
);
CREATE TABLE IF NOT EXISTS forecasts (
  run_id BIGINT NOT NULL,
  forecast_date DATE NOT NULL,
  product_id VARCHAR(64) NOT NULL,
  store_id VARCHAR(64),
  expected_units DECIMAL(14,3) NOT NULL,
  lower_units DECIMAL(14,3),
  upper_units DECIMAL(14,3),
  PRIMARY KEY (run_id, forecast_date, product_id),
  FOREIGN KEY (run_id) REFERENCES model_runs(run_id),
  FOREIGN KEY (product_id) REFERENCES products(product_id),
  FOREIGN KEY (store_id) REFERENCES stores(store_id)
);
CREATE TABLE IF NOT EXISTS forecast_metrics (
  run_id BIGINT NOT NULL,
  fold_num SMALLINT NOT NULL,
  model_name VARCHAR(100) NOT NULL,
  mae DECIMAL(14,4),
  rmse DECIMAL(14,4),
  wape DECIMAL(14,4),
  bias_units DECIMAL(14,4),
  PRIMARY KEY (run_id, fold_num, model_name),
  FOREIGN KEY (run_id) REFERENCES model_runs(run_id)
);
CREATE TABLE IF NOT EXISTS inventory_recommendations (
  recommendation_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  snapshot_date DATE NOT NULL,
  product_id VARCHAR(64) NOT NULL,
  store_id VARCHAR(64) NOT NULL,
  safety_stock DECIMAL(14,2) NOT NULL,
  reorder_point DECIMAL(14,2) NOT NULL,
  suggested_order DECIMAL(14,2) NOT NULL,
  risk_level VARCHAR(16) NOT NULL,
  reason VARCHAR(500) NOT NULL,
  FOREIGN KEY (product_id) REFERENCES products(product_id),
  FOREIGN KEY (store_id) REFERENCES stores(store_id)
);
CREATE TABLE IF NOT EXISTS alerts (
  alert_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  created_at DATETIME NOT NULL,
  severity VARCHAR(16) NOT NULL,
  product_id VARCHAR(64),
  store_id VARCHAR(64),
  title VARCHAR(255) NOT NULL,
  detail TEXT NOT NULL,
  FOREIGN KEY (product_id) REFERENCES products(product_id),
  FOREIGN KEY (store_id) REFERENCES stores(store_id)
);
CREATE TABLE IF NOT EXISTS data_quality_runs (
  quality_run_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  created_at DATETIME NOT NULL,
  dataset_checksum CHAR(64) NOT NULL,
  row_count BIGINT NOT NULL,
  health_score TINYINT NOT NULL,
  checks_json JSON NOT NULL,
  CHECK (health_score BETWEEN 0 AND 100)
);
