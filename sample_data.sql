INSERT INTO
  zsm_data.product_group(pg_name, pg_department, pg_slug)
VALUES
  ('Evil Currency', 'E-Corp', 'evil-currency');

INSERT INTO
  zsm_data.product(p_product_group_id, p_name, p_slug, p_delivery_team)
VALUES
  ((select pg_id from zsm_data.product_group where pg_name='Evil Currency'), 'E-Coin', 'e-coin', 'Dark Army');

INSERT INTO
  zsm_data.service_level_objective(slo_product_id, slo_title)
VALUES
  ((select p_id from zsm_data.product where p_name='E-Coin'), 'More than 95% successful responses under 200ms'),
  ((select p_id from zsm_data.product where p_name='E-Coin'), 'More than 99% successful responses under 1000ms');

INSERT INTO
  zsm_data.service_level_indicator_target(slit_slo_id, slit_sli_name, slit_to, slit_unit)
VALUES
  ((select slo_id from zsm_data.service_level_objective where slo_title like '%95%'), 'latency.p95', '200', 'ms'),
  ((select slo_id from zsm_data.service_level_objective where slo_title like '%99%'), 'latency.p99', '1000', 'ms');


