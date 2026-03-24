"""
OwlDB — supply-owl 的 SQLite 数据层

职责：
1. 建表 (schema.sql)
2. 从 supply-cli JSON 快照导入
3. CRUD 查询
"""
import json
import sqlite3
import time
from pathlib import Path
from typing import Optional

from .models import ContractBatch, CollabCase, ContractMeta, ProgressNote

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


class OwlDB:
    def __init__(self, db_path: str = "owl.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript(SCHEMA_PATH.read_text())
        self.conn.commit()

    def close(self):
        self.conn.close()

    # ── 导入 supply-cli JSON 快照 ────────────────────

    def import_snapshot(self, snapshot_path: str) -> dict:
        """从 supply-cli 的 JSON 快照文件导入数据，返回导入统计"""
        data = json.loads(Path(snapshot_path).read_text())
        if data.get("version") != 1:
            raise ValueError(f"不支持的快照版本: {data.get('version')}")

        batches = data.get("contractBatches", [])
        cases = data.get("collabCases", [])
        metas = data.get("contractMeta", [])

        batch_count = self._upsert_batches(batches)
        case_count = self._upsert_cases(cases)
        meta_count = self._upsert_metas(metas)

        now = int(time.time() * 1000)
        self.conn.execute(
            "INSERT OR REPLACE INTO sync_meta (key, value, updated_at) VALUES (?, ?, ?)",
            ("last_snapshot_import", snapshot_path, now),
        )
        self.conn.commit()

        return {
            "batches": batch_count,
            "cases": case_count,
            "metas": meta_count,
            "snapshot": snapshot_path,
        }

    def _upsert_batches(self, batches: list[dict]) -> int:
        sql = """
        INSERT OR REPLACE INTO contract_batch (
            key, contract_no, batch_no, project_name, customer, iso,
            product_coa, dispatcher, order_confirm_date, rpd, cpd, epd_a, apd,
            supply_manager, fc_handler, coordinator, representative,
            complete_no, demand_status, promise_status, promise_status_str,
            short_item, product_coa_number, physical_flag, sub1_amount,
            urgent_flag, related_contract_no, related_batch_no, related_batch_epd_a,
            last_updated
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """
        rows = []
        for b in batches:
            rows.append((
                b.get("key", f"{b['contractNo']}_{b['batchNo']}"),
                b["contractNo"], b["batchNo"],
                b.get("projectName"), b.get("customer"), b.get("iso"),
                b.get("productCoa"), b.get("dispatcher"),
                b.get("orderConfirmDate"), b.get("rpd"), b.get("cpd"),
                b.get("epdA"), b.get("apd"),
                b.get("supplyManager"), b.get("fcHandler"),
                b.get("coordinator"), b.get("representative"),
                b.get("completeNo"), b.get("demandStatus"),
                b.get("promiseStatus"), b.get("promiseStatusStr"),
                b.get("shortItem"), b.get("productCoaNumber"),
                b.get("physicalFlag"), b.get("sub1Amount"),
                b.get("urgentFlag"), b.get("relatedContractNo"),
                b.get("relatedBatchNo"), b.get("relatedBatchEpdA"),
                b.get("lastUpdated", 0),
            ))
        self.conn.executemany(sql, rows)
        return len(rows)

    def _upsert_cases(self, cases: list[dict]) -> int:
        sql = """
        INSERT OR REPLACE INTO collab_case (
            case_id, type, contract_no, batch_no, source_id, status,
            handler, title, created_at, updated_at, closed_at,
            first_seen_at, last_seen_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        rows = []
        for c in cases:
            rows.append((
                c["caseId"], c["type"], c["contractNo"],
                c.get("batchNo"), c.get("sourceId", ""), c.get("status", ""),
                c.get("handler"), c.get("title", ""),
                c.get("createdAt", 0), c.get("updatedAt", 0), c.get("closedAt"),
                c.get("firstSeenAt", 0), c.get("lastSeenAt"),
            ))
        self.conn.executemany(sql, rows)
        return len(rows)

    def _upsert_metas(self, metas: list[dict]) -> int:
        sql = """
        INSERT OR REPLACE INTO contract_meta (
            contract, project_name, iso, last_seen, user_viewed_ts
        ) VALUES (?, ?, ?, ?, ?)
        """
        rows = []
        for m in metas:
            rows.append((
                m["contract"], m.get("projectName"), m.get("iso"),
                m.get("lastSeen", 0), m.get("userViewedTs"),
            ))
        self.conn.executemany(sql, rows)
        return len(rows)

    # ── 查询 ────────────────────────────────────────

    def get_all_batches(self, contract_no: Optional[str] = None) -> list[ContractBatch]:
        if contract_no:
            rows = self.conn.execute(
                "SELECT * FROM contract_batch WHERE contract_no = ? ORDER BY batch_no",
                (contract_no,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM contract_batch ORDER BY contract_no, batch_no",
            ).fetchall()
        return [self._row_to_batch(r) for r in rows]

    def get_contracts_summary(self) -> list[dict]:
        """按合同聚合，返回每个合同的概要"""
        rows = self.conn.execute("""
            SELECT contract_no,
                   MIN(project_name) as project_name,
                   MIN(customer) as customer,
                   COUNT(*) as batch_count,
                   GROUP_CONCAT(DISTINCT dispatcher) as dispatchers,
                   GROUP_CONCAT(DISTINCT supply_manager) as supply_managers,
                   MIN(rpd) as earliest_rpd,
                   SUM(CASE WHEN cpd IS NULL THEN 1 ELSE 0 END) as uncommitted_count,
                   SUM(CASE WHEN short_item IS NOT NULL AND short_item != '' THEN 1 ELSE 0 END) as shortage_count,
                   SUM(CASE WHEN urgent_flag = '1' OR urgent_flag = 'Y' THEN 1 ELSE 0 END) as urgent_count
            FROM contract_batch
            GROUP BY contract_no
            ORDER BY contract_no
        """).fetchall()
        return [dict(r) for r in rows]

    def get_batches_by_dispatcher(self, dispatcher: str) -> list[ContractBatch]:
        rows = self.conn.execute(
            "SELECT * FROM contract_batch WHERE dispatcher = ? ORDER BY rpd",
            (dispatcher,),
        ).fetchall()
        return [self._row_to_batch(r) for r in rows]

    def get_batches_by_supply_manager(self, supply_manager: str) -> list[ContractBatch]:
        rows = self.conn.execute(
            "SELECT * FROM contract_batch WHERE supply_manager = ? ORDER BY rpd",
            (supply_manager,),
        ).fetchall()
        return [self._row_to_batch(r) for r in rows]

    def get_collab_cases(self, contract_no: Optional[str] = None) -> list[CollabCase]:
        if contract_no:
            rows = self.conn.execute(
                "SELECT * FROM collab_case WHERE contract_no = ? ORDER BY updated_at DESC",
                (contract_no,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM collab_case WHERE status != 'closed' ORDER BY updated_at DESC",
            ).fetchall()
        return [self._row_to_case(r) for r in rows]

    # ── 进展记录 ────────────────────────────────────

    def add_progress_note(self, note: ProgressNote) -> int:
        cur = self.conn.execute(
            """INSERT INTO progress_note
               (contract_no, batch_no, contact, content, parsed_summary, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (note.contract_no, note.batch_no, note.contact,
             note.content, note.parsed_summary, note.created_at or int(time.time() * 1000)),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_progress_notes(self, contract_no: Optional[str] = None, limit: int = 50) -> list[ProgressNote]:
        if contract_no:
            rows = self.conn.execute(
                "SELECT * FROM progress_note WHERE contract_no = ? ORDER BY created_at DESC LIMIT ?",
                (contract_no, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM progress_note ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [ProgressNote(
            id=r["id"], contract_no=r["contract_no"], batch_no=r["batch_no"],
            contact=r["contact"], content=r["content"],
            parsed_summary=r["parsed_summary"], created_at=r["created_at"],
        ) for r in rows]

    # ── 同步信息 ────────────────────────────────────

    def get_sync_info(self) -> dict:
        rows = self.conn.execute("SELECT * FROM sync_meta").fetchall()
        return {r["key"]: {"value": r["value"], "updated_at": r["updated_at"]} for r in rows}

    # ── 内部转换 ────────────────────────────────────

    @staticmethod
    def _row_to_batch(row: sqlite3.Row) -> ContractBatch:
        return ContractBatch(
            key=row["key"], contract_no=row["contract_no"], batch_no=row["batch_no"],
            project_name=row["project_name"], customer=row["customer"], iso=row["iso"],
            product_coa=row["product_coa"], dispatcher=row["dispatcher"],
            order_confirm_date=row["order_confirm_date"],
            rpd=row["rpd"], cpd=row["cpd"], epd_a=row["epd_a"], apd=row["apd"],
            supply_manager=row["supply_manager"], fc_handler=row["fc_handler"],
            coordinator=row["coordinator"], representative=row["representative"],
            complete_no=row["complete_no"], demand_status=row["demand_status"],
            promise_status=row["promise_status"], promise_status_str=row["promise_status_str"],
            short_item=row["short_item"], product_coa_number=row["product_coa_number"],
            physical_flag=row["physical_flag"], sub1_amount=row["sub1_amount"],
            urgent_flag=row["urgent_flag"],
            related_contract_no=row["related_contract_no"],
            related_batch_no=row["related_batch_no"],
            related_batch_epd_a=row["related_batch_epd_a"],
            last_updated=row["last_updated"],
        )

    @staticmethod
    def _row_to_case(row: sqlite3.Row) -> CollabCase:
        return CollabCase(
            case_id=row["case_id"], type=row["type"],
            contract_no=row["contract_no"], batch_no=row["batch_no"],
            source_id=row["source_id"], status=row["status"],
            handler=row["handler"], title=row["title"],
            created_at=row["created_at"], updated_at=row["updated_at"],
            closed_at=row["closed_at"],
            first_seen_at=row["first_seen_at"], last_seen_at=row["last_seen_at"],
        )
