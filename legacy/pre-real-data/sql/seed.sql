USE retailmind;
-- Reference dimensions only. Generate sales with scripts/generate_demo.py or upload a CSV.
INSERT IGNORE INTO categories (category_id, category_name) VALUES
('Grocery','Grocery'),('Apparel','Apparel'),('Electronics','Electronics'),
('Home','Home'),('Beauty','Beauty'),('Sports','Sports');
INSERT IGNORE INTO regions (region_id, region_name) VALUES
('North','North'),('South','South'),('East','East'),('West','West');
INSERT IGNORE INTO suppliers (supplier_id, supplier_name) VALUES
('SUP-01','Supplier 01'),('SUP-02','Supplier 02'),('SUP-03','Supplier 03'),
('SUP-04','Supplier 04'),('SUP-05','Supplier 05'),('SUP-06','Supplier 06'),
('SUP-07','Supplier 07'),('SUP-08','Supplier 08'),('SUP-09','Supplier 09');
