CREATE DATABASE IF NOT EXISTS retailmind CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE retailmind;

CREATE TABLE IF NOT EXISTS products (
  product_id VARCHAR(32) PRIMARY KEY,
  product VARCHAR(255) NOT NULL,
  category VARCHAR(100) NOT NULL,
  supplier VARCHAR(100)
);
CREATE TABLE IF NOT EXISTS stores (
  store_id VARCHAR(32) PRIMARY KEY,
  store VARCHAR(255) NOT NULL,
  region VARCHAR(100) NOT NULL
);
CREATE TABLE IF NOT EXISTS sales (
  date DATE NOT NULL,
  product_id VARCHAR(32) NOT NULL,
  store_id VARCHAR(32) NOT NULL,
  units DECIMAL(14,2) NOT NULL,
  price DECIMAL(14,2) NOT NULL,
  discount DECIMAL(5,4) DEFAULT 0,
  promotion BOOLEAN DEFAULT FALSE,
  returns DECIMAL(14,2) DEFAULT 0,
  PRIMARY KEY (date, product_id, store_id),
  FOREIGN KEY (product_id) REFERENCES products(product_id),
  FOREIGN KEY (store_id) REFERENCES stores(store_id)
);
CREATE TABLE IF NOT EXISTS inventory (
  snapshot_date DATE NOT NULL,
  product_id VARCHAR(32) NOT NULL,
  store_id VARCHAR(32) NOT NULL,
  stock DECIMAL(14,2) NOT NULL,
  lead_time INT NOT NULL,
  PRIMARY KEY (snapshot_date, product_id, store_id),
  FOREIGN KEY (product_id) REFERENCES products(product_id),
  FOREIGN KEY (store_id) REFERENCES stores(store_id)
);
CREATE TABLE IF NOT EXISTS forecast_runs (
  run_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  product_id VARCHAR(32) NOT NULL,
  store_id VARCHAR(32),
  trained_at DATETIME NOT NULL,
  dataset_version VARCHAR(64) NOT NULL,
  model_name VARCHAR(100) NOT NULL,
  wape DECIMAL(10,4)
);
