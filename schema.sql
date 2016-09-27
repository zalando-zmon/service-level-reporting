CREATE SCHEMA IF NOT EXISTS zsm_data;

CREATE TABLE IF NOT EXISTS zsm_data.product_group (
    pg_id serial PRIMARY KEY,
    pg_name text not null,
    pg_slug text not null UNIQUE,
    pg_department text
);

CREATE TABLE IF NOT EXISTS zsm_data.product (
    p_id serial PRIMARY KEY,
    p_product_group_id int references zsm_data.product_group(pg_id),
    p_name text not null,
    p_slug text not null UNIQUE,
    p_delivery_team text
);

CREATE TABLE IF NOT EXISTS zsm_data.service_level_objective (
    slo_id serial PRIMARY KEY,
    slo_title text not null,
    slo_product_id int references zsm_data.product(p_id)
);

CREATE TABLE IF NOT EXISTS zsm_data.service_level_indicator_target (
    slit_slo_id int references zsm_data.service_level_objective(slo_id),
    slit_sli_name text not null,
    slit_unit text,
    slit_from real,
    slit_to real,
    PRIMARY KEY (slit_slo_id, slit_sli_name)
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
