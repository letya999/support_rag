CREATE TABLE IF NOT EXISTS webhooks (
  webhook_id VARCHAR(36) PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  description TEXT,
  url VARCHAR(2048) NOT NULL,
  events TEXT, -- JSON array of event types
  secret_hash VARCHAR(255) NOT NULL, -- HMAC-SHA256
  active BOOLEAN DEFAULT TRUE,
  ip_whitelist TEXT, -- JSON array of IP/CIDR
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  created_by VARCHAR(255),
  metadata JSONB,

  UNIQUE(url)
);

CREATE INDEX IF NOT EXISTS idx_webhooks_active ON webhooks(active);
CREATE INDEX IF NOT EXISTS idx_webhooks_created_at ON webhooks(created_at);

CREATE TABLE IF NOT EXISTS webhook_deliveries (
  delivery_id VARCHAR(36) PRIMARY KEY,
  webhook_id VARCHAR(36) NOT NULL REFERENCES webhooks(webhook_id) ON DELETE CASCADE,
  event_id VARCHAR(36) NOT NULL,
  event_type VARCHAR(255) NOT NULL,
  payload JSONB NOT NULL,
  status VARCHAR(50), -- pending, queued, sent, success, failed
  http_status INT,
  response_body TEXT,
  attempt INT DEFAULT 1,
  max_attempts INT DEFAULT 7,
  next_retry TIMESTAMP,
  error_message TEXT,
  response_time_ms INT,
  created_at TIMESTAMP DEFAULT NOW(),
  delivered_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_wd_status ON webhook_deliveries(status);
CREATE INDEX IF NOT EXISTS idx_wd_webhook_id ON webhook_deliveries(webhook_id);
CREATE INDEX IF NOT EXISTS idx_wd_created_at ON webhook_deliveries(created_at);
CREATE INDEX IF NOT EXISTS idx_wd_next_retry ON webhook_deliveries(next_retry);
