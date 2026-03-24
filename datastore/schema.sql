-- supply-owl SQLite schema
-- 对齐 supply-cli types.ts + supply-owl 自有表

-- ============================================================
-- 合同批次（来自 supply-cli，定时同步）
-- ============================================================
CREATE TABLE IF NOT EXISTS contract_batch (
    key             TEXT PRIMARY KEY,   -- contractNo + batchNo
    contract_no     TEXT NOT NULL,
    batch_no        TEXT NOT NULL,
    project_name    TEXT,
    customer        TEXT,
    iso             TEXT,
    product_coa     TEXT,
    dispatcher      TEXT,               -- 大调度
    order_confirm_date TEXT,
    rpd             TEXT,               -- 需求计划日期
    cpd             TEXT,               -- 承诺交付日期
    epd_a           TEXT,               -- EPD-A
    apd             TEXT,               -- 实际交单日期
    supply_manager  TEXT,               -- 供应经理
    fc_handler      TEXT,
    coordinator     TEXT,               -- 资源统筹
    representative  TEXT,
    complete_no     TEXT,
    demand_status   TEXT,
    promise_status  INTEGER,
    promise_status_str TEXT,
    short_item      TEXT,               -- 欠料标识
    product_coa_number TEXT,
    physical_flag   TEXT,
    sub1_amount     TEXT,
    urgent_flag     TEXT,               -- 急单标识
    related_contract_no TEXT,
    related_batch_no TEXT,
    related_batch_epd_a TEXT,
    last_updated    INTEGER NOT NULL DEFAULT 0  -- timestamp ms
);

CREATE INDEX IF NOT EXISTS idx_cb_contract ON contract_batch(contract_no);
CREATE INDEX IF NOT EXISTS idx_cb_dispatcher ON contract_batch(dispatcher);
CREATE INDEX IF NOT EXISTS idx_cb_supply_manager ON contract_batch(supply_manager);
CREATE INDEX IF NOT EXISTS idx_cb_rpd ON contract_batch(rpd);

-- ============================================================
-- 协同工单（来自 supply-cli）
-- ============================================================
CREATE TABLE IF NOT EXISTS collab_case (
    case_id         TEXT PRIMARY KEY,
    type            TEXT NOT NULL,
    contract_no     TEXT NOT NULL,
    batch_no        TEXT,
    source_id       TEXT,
    status          TEXT,
    handler         TEXT,
    title           TEXT,
    created_at      INTEGER NOT NULL DEFAULT 0,
    updated_at      INTEGER NOT NULL DEFAULT 0,
    closed_at       INTEGER,
    first_seen_at   INTEGER NOT NULL DEFAULT 0,
    last_seen_at    INTEGER
);

CREATE INDEX IF NOT EXISTS idx_cc_contract ON collab_case(contract_no);
CREATE INDEX IF NOT EXISTS idx_cc_status ON collab_case(status);

-- ============================================================
-- 合同元数据（来自 supply-cli）
-- ============================================================
CREATE TABLE IF NOT EXISTS contract_meta (
    contract        TEXT PRIMARY KEY,
    project_name    TEXT,
    iso             TEXT,
    last_seen       INTEGER NOT NULL DEFAULT 0,
    user_viewed_ts  INTEGER
);

-- ============================================================
-- 进展记录（supply-owl 自有，碎片录入 → LLM 解析）
-- ============================================================
CREATE TABLE IF NOT EXISTS progress_note (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_no     TEXT NOT NULL,
    batch_no        TEXT,
    contact         TEXT NOT NULL,       -- 谁回复的
    content         TEXT NOT NULL,       -- 原文
    parsed_summary  TEXT DEFAULT '',     -- LLM 解析后的摘要
    created_at      INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_pn_contract ON progress_note(contract_no);
CREATE INDEX IF NOT EXISTS idx_pn_contact_name ON progress_note(contact);

-- ============================================================
-- 同步元数据（记录最后同步时间）
-- ============================================================
CREATE TABLE IF NOT EXISTS sync_meta (
    key             TEXT PRIMARY KEY,
    value           TEXT,
    updated_at      INTEGER NOT NULL DEFAULT 0
);
