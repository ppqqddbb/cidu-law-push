"""Synchronize PostgreSQL cases marked 是否同步到知识库=是 to Dify."""
import argparse, hashlib, json, logging, os
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent
CFG = ROOT / "kb_sync.local.json"
FIELDS = "fid, fk_r8p0_title, fk_r8p0_source, fk_r8p0_link, fk_r8p0_date, fk_r8p0_file_date, fk_r8p0_summary"

def load():
    c = json.loads(CFG.read_text(encoding="utf-8-sig"))
    c["dify"]["api_key"] = os.getenv("DIFY_KB_API_KEY", c["dify"].get("api_key", ""))
    return c

def value(row, key, index):
    """Read either psycopg dict rows or ordinary tuple rows."""
    if hasattr(row, "get"):
        return row.get(key)
    return row[index]


def content(r):
    return "\n".join(f"{k}：{value(r, field, index) or ''}" for k, field, index in [
        ("标题", "fk_r8p0_title", 1), ("来源", "fk_r8p0_source", 2),
        ("链接", "fk_r8p0_link", 3), ("日期", "fk_r8p0_date", 4),
        ("文件日期", "fk_r8p0_file_date", 5), ("摘要", "fk_r8p0_summary", 6)])

def main():
    p=argparse.ArgumentParser(); p.add_argument("--dry-run",action="store_true"); p.add_argument("--limit",type=int,default=100); a=p.parse_args()
    logging.basicConfig(level=logging.INFO,format="%(asctime)s [%(levelname)s] %(message)s"); c=load(); d=c["database"]; f=c["dify"]
    if not f.get("api_key"): raise SystemExit("请在 kb_sync.local.json 填写 Dify API 密钥")
    table=d.get("table") or "tk_r8p0_case"; schema=d.get("schema") or "public"
    if not table.replace("_","").isalnum(): raise SystemExit("表名无效")
    try:
        import psycopg
    except ImportError:
        raise SystemExit("缺少 psycopg，请执行: pip install -r requirements_kb.txt")
    with psycopg.connect(host=d["host"],port=d["port"],dbname=d["database"],user=d["user"],password=d["password"],row_factory=psycopg.rows.dict_row) as db:
        rows=db.execute(f'SELECT {FIELDS} FROM "{schema}"."{table}" WHERE fk_r8p0_sync_kb=%s ORDER BY fid LIMIT %s',("是",a.limit)).fetchall()
        if a.dry_run: logging.info("待同步 %d 条",len(rows)); return 0
        h={"Authorization":"Bearer "+f["api_key"],"Content-Type":"application/json"}; base=f["base_url"].rstrip("/"); ds=f.get("dataset_id")
        if not ds:
            x=requests.get(base+"/datasets",headers=h,params={"page":1,"limit":100},timeout=30); x.raise_for_status(); found=[x for x in x.json().get("data",[]) if x.get("name")==f["dataset_name"]]
            if len(found)!=1: raise SystemExit("未找到唯一知识库，请在配置填写 dataset_id")
            ds=found[0]["id"]
        for r in rows:
            fid = value(r, "fid", 0)
            title = value(r, "fk_r8p0_title", 1)
            body={"name":f"case-{fid}","text":content(r),"indexing_technique":"high_quality","process_rule":{"mode":"automatic"}}
            try:
                x=requests.post(f"{base}/datasets/{ds}/document/create-by-text",headers=h,json=body,timeout=60); x.raise_for_status(); j=x.json()
                if not j.get("document") and not j.get("data"): raise RuntimeError("Dify 未返回文档")
            except Exception as e: logging.error("fid=%s 同步失败：%s",fid,e); continue
            db.execute(f'UPDATE "{schema}"."{table}" SET fk_r8p0_sync_kb=%s WHERE fid=%s',("否",fid)); db.commit(); logging.info("fid=%s 已同步",fid)
    return 0
if __name__ == "__main__": raise SystemExit(main())
