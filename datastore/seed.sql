-- supply-owl 测试数据 — 贴近真实业务场景
-- 5 个合同，覆盖：未承诺/CPD不满足/已交单/正常/急单/欠料

-- ============================================================
-- 合同1: 中国移动 江苏城域网扩容 — 2个批次，1个未承诺+急单+欠料
-- ============================================================
INSERT OR REPLACE INTO contract_batch VALUES (
    '1Y01052508474L_B001', '1Y01052508474L', 'B001',
    '江苏移动城域网扩容', '中国移动', 'CN', 'OptiX OSN 9800',
    '张工',  -- dispatcher
    '2026-02-15',  -- orderConfirmDate
    '2026-03-29',  -- rpd
    NULL,          -- cpd: 未承诺！
    NULL, NULL,
    '李经理',  -- supplyManager
    '刘主管',  -- fcHandler
    '陈工',    -- coordinator
    '赵代表',  -- representative
    NULL,
    '待处理',  -- demandStatus
    0, '未承诺',
    'Y',       -- shortItem: 欠料
    'OSN9800-V300R023', NULL, NULL,
    '1',       -- urgentFlag: 急单
    NULL, NULL, NULL,
    1711267200000
);

INSERT OR REPLACE INTO contract_batch VALUES (
    '1Y01052508474L_B002', '1Y01052508474L', 'B002',
    '江苏移动城域网扩容', '中国移动', 'CN', 'OptiX OSN 9800',
    '张工', '2026-02-15',
    '2026-04-15',  -- rpd
    '2026-04-10',  -- cpd: 满足RPD
    NULL, NULL,
    '李经理', '刘主管', '陈工', '赵代表', NULL,
    '正常', 1, '已承诺',
    NULL, 'OSN9800-V300R023', NULL, NULL,
    NULL, NULL, NULL, NULL,
    1711267200000
);

-- ============================================================
-- 合同2: Vodafone 德国5G回传 — CPD不满足RPD + 欠料
-- ============================================================
INSERT OR REPLACE INTO contract_batch VALUES (
    '1Y02893760876C_B001', '1Y02893760876C', 'B001',
    '德国5G回传', 'Vodafone', 'DE', 'OptiX OSN 1800',
    '张工', '2026-01-20',
    '2026-04-03',  -- rpd
    '2026-04-11',  -- cpd: 比RPD晚8天
    '2026-03-15', NULL,
    '王经理', NULL, '陈工', NULL, NULL,
    '提拉中', 1, '已承诺',
    'Y', 'OSN1800-V100R022', NULL, NULL,
    NULL,
    '00E738291A', 'HWA001', '2026-04-05',  -- 关联合同
    1711267200000
);

-- ============================================================
-- 合同3: Telefonica 西班牙光网改造 — HWA批次 + CPD不满足 + 欠料
-- ============================================================
INSERT OR REPLACE INTO contract_batch VALUES (
    '1Y04567891234D_HWA001', '1Y04567891234D', 'HWA001',
    '西班牙光网改造', 'Telefonica', 'ES', 'NetEngine 8000',
    '王工', '2025-12-10',
    '2026-03-21',  -- rpd
    '2026-03-28',  -- cpd: 比RPD晚7天
    '2026-03-01', NULL,
    '王经理', NULL, '李工', NULL, NULL,
    '提拉中', 1, '已承诺',
    'Y', 'NE8000-X8', NULL, NULL,
    '1',  -- 急单
    NULL, NULL, NULL,
    1711267200000
);

-- ============================================================
-- 合同4: Deutsche Telekom DT核心路由器 — 正常，CPD满足RPD
-- ============================================================
INSERT OR REPLACE INTO contract_batch VALUES (
    '1Y05678901234E_B001', '1Y05678901234E', 'B001',
    'DT核心路由器替换', 'Deutsche Telekom', 'DE', 'NetEngine 8000',
    '王工', '2026-01-05',
    '2026-04-08',  -- rpd
    '2026-04-05',  -- cpd: 满足RPD
    '2026-03-20', NULL,
    '赵经理', NULL, NULL, NULL, NULL,
    '正常', 1, '已承诺',
    NULL, 'NE8000-X4', NULL, NULL,
    NULL, NULL, NULL, NULL,
    1711267200000
);

-- ============================================================
-- 合同5: 中国电信 浙江数据中心 — 未承诺 + 欠料 + 2个批次
-- ============================================================
INSERT OR REPLACE INTO contract_batch VALUES (
    '1Y06789012345F_B001', '1Y06789012345F', 'B001',
    '浙江电信数据中心', '中国电信', 'CN', 'OceanStor 5300',
    '赵工', '2026-02-01',
    '2026-03-31',  -- rpd
    NULL,          -- cpd: 未承诺
    NULL, NULL,
    '孙经理', NULL, '李工', NULL, NULL,
    '待处理', 0, '未承诺',
    'Y', 'OceanStor5300-V300', NULL, NULL,
    NULL, NULL, NULL, NULL,
    1711267200000
);

INSERT OR REPLACE INTO contract_batch VALUES (
    '1Y06789012345F_B002', '1Y06789012345F', 'B002',
    '浙江电信数据中心', '中国电信', 'CN', 'OceanStor 5300',
    '赵工', '2026-02-01',
    '2026-04-20',  -- rpd
    '2026-04-18',  -- cpd: 满足
    NULL, NULL,
    '孙经理', NULL, '李工', NULL, NULL,
    '正常', 1, '已承诺',
    NULL, 'OceanStor5300-V300', NULL, NULL,
    NULL, NULL, NULL, NULL,
    1711267200000
);

-- ============================================================
-- 协同工单
-- ============================================================
INSERT OR REPLACE INTO collab_case VALUES (
    'CASE-2026-001', 'expedite', '1Y01052508474L', 'B001',
    'WL-MSG-001', 'open', '张工',
    '100G光模块缺料，需提拉承诺',
    1711180800000, 1711267200000, NULL, 1711180800000, 1711267200000
);

INSERT OR REPLACE INTO collab_case VALUES (
    'CASE-2026-002', 'expedite', '1Y02893760876C', 'B001',
    'WL-MSG-002', 'open', '王经理',
    'DC电源模块欠料5个，CPD不满足RPD',
    1711094400000, 1711267200000, NULL, 1711094400000, 1711267200000
);

INSERT OR REPLACE INTO collab_case VALUES (
    'CASE-2026-003', 'risk', '1Y04567891234D', 'HWA001',
    'WL-MSG-003', 'open', '王工',
    '西班牙项目急单，AC电源模块缺料10个',
    1711008000000, 1711267200000, NULL, 1711008000000, 1711267200000
);

-- ============================================================
-- 合同元数据
-- ============================================================
INSERT OR REPLACE INTO contract_meta VALUES ('1Y01052508474L', '江苏移动城域网扩容', 'CN', 1711267200000, 1711180800000);
INSERT OR REPLACE INTO contract_meta VALUES ('1Y02893760876C', '德国5G回传', 'DE', 1711267200000, 1711094400000);
INSERT OR REPLACE INTO contract_meta VALUES ('1Y04567891234D', '西班牙光网改造', 'ES', 1711267200000, NULL);
INSERT OR REPLACE INTO contract_meta VALUES ('1Y05678901234E', 'DT核心路由器替换', 'DE', 1711267200000, NULL);
INSERT OR REPLACE INTO contract_meta VALUES ('1Y06789012345F', '浙江电信数据中心', 'CN', 1711267200000, 1711267200000);

-- ============================================================
-- 模拟进展记录
-- ============================================================
INSERT INTO progress_note (contract_no, batch_no, contact, content, parsed_summary, created_at) VALUES
    ('1Y01052508474L', 'B001', '大调度 张工', '100G光模块东莞仓有库存，可以调拨，预计周三到', '100G光模块 ETA 周三，来源东莞仓调拨', 1711180800000),
    ('1Y02893760876C', 'B001', '供应经理 王经理', 'DC电源模块供应商说周五能出5个，但要走深圳仓中转', 'DC电源模块 x5 ETA 周五，经深圳仓中转', 1711094400000),
    ('1Y04567891234D', 'HWA001', '大调度 王工', '排产已经安排了，但AC电源模块还在等料，预计下周一', 'AC电源模块排产已安排，等料中 ETA 下周一', 1711008000000);
