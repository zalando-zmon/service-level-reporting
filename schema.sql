CREATE SCHEMA IF NOT EXISTS zsm_data;

CREATE TABLE IF NOT EXISTS zsm_data.product_group (
    pg_id serial PRIMARY KEY,
    pg_name text not null,
    pg_department text
);

CREATE TABLE IF NOT EXISTS zsm_data.product (
    p_id serial PRIMARY KEY,
    p_product_group_id int references zsm_data.product_group(pg_id),
    p_name text not null,
    p_delivery_team text
);

CREATE TABLE IF NOT EXISTS zsm_data.service_level_objective (
    slo_product_id int references zsm_data.product(p_id),
    slo_service_level_indicator text not null,
    slo_target_unit text,
    slo_target_from real,
    slo_target_to real
);

CREATE TABLE IF NOT EXISTS zsm_data.service_level_indicator (
    sli_product_id int references zsm_data.product(p_id),
    sli_name text,
    sli_timestamp timestamp,
    sli_value real,
    PRIMARY KEY (sli_product_id, sli_name, sli_timestamp)
);

CREATE TABLE IF NOT EXISTS zsm_data.data_source (
    ds_product_id integer REFERENCES zsm_data.product(p_id),
    ds_sli_name text,
    ds_definition jsonb,
    PRIMARY KEY (ds_product_id, ds_sli_name)
);
