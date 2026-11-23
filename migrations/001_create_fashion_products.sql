-- Initial schema for the Fashion Studio ETL pipeline destination table.
-- Executed automatically by PostgreSQL docker-entrypoint-initdb.d on first startup.

CREATE TABLE IF NOT EXISTS fashion_products (
    id BIGSERIAL PRIMARY KEY,
    "Title" TEXT NOT NULL,
    "Price" NUMERIC(14, 2) NOT NULL CHECK ("Price" >= 0),
    "Rating" DOUBLE PRECISION NOT NULL CHECK ("Rating" >= 0 AND "Rating" <= 5),
    "Colors" INTEGER NOT NULL CHECK ("Colors" >= 0),
    "Size" VARCHAR(32) NOT NULL,
    "Gender" VARCHAR(32) NOT NULL,
    "timestamp" TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fashion_products_timestamp
    ON fashion_products ("timestamp" DESC);
