#!/usr/bin/env python3
"""MiniMax international API PAYG balance preflight, GET ONLY.

No TTS calls, no paid usage, no credential values, no account identifiers.
Print only whether promotional/voucher credits are present and whether API
balance can be determined; keep financial amounts out of public issue.
"""
import json, os
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from run_male_prague import post_comment, StopTest

URL = "https://api.minimax.io/account/query_balance"

def nonnegative_number(item):
    if item is None: return None
    try:
        v=Decimal(str(item))
        if not v.is_finite(): return None
        return v
    except (InvalidOperation,ValueError):return None

def main():
    key=os.environ.get("MINIMAX_API_KEY","").strip()
    if not key:raise StopTest("MiniMax key not configured")
    if not key.startswith("sk-api-"):
        post_comment("MINIMAX BALANCE READ-ONLY: present key is not confirmed PAYG format; no quota query and no synthesis.")
        return
    req=Request(URL,headers={"Authorization":"Bearer "+key,"Accept":"application/json"},method="GET")
    try:
        with urlopen(req,timeout=25) as r:
            if r.status!=200:raise StopTest("Unexpected MiniMax balance status")
            payload=json.load(r)
    except HTTPError as e:
        post_comment("MINIMAX BALANCE READ-ONLY: HTTP "+str(e.code)+". No synthesis attempted.")
        return
    except URLError:
        post_comment("MINIMAX BALANCE READ-ONLY: network failure. No synthesis attempted.")
        return
    if not isinstance(payload,dict):
        raise StopTest("Unexpected MiniMax balance JSON shape")
    base=payload.get("base_resp") or {}
    if isinstance(base,dict) and base.get("status_code") not in (0,None):
        post_comment("MINIMAX BALANCE READ-ONLY: provider returned non-success. No synthesis attempted.")
        return
    # Newer global responses may nest balances in data; do not infer zero
    # if a field is missing.  Report only positive/zero/unknown, not amounts.
    record=payload.get("data") if isinstance(payload.get("data"),dict) else payload
    statuses={}
    for name in ("available_amount","cash_balance","voucher_balance","credit_balance","owed_amount"):
        amount=nonnegative_number(record.get(name))
        statuses[name]="unknown" if amount is None else "positive" if amount>0 else "zero"
    post_comment("MINIMAX BALANCE READ-ONLY: "+json.dumps(
        {"endpoint":"PAYG GET account/query_balance",
         "balance_categories":statuses,"new_TTS":False,"paid_calls":0,
         "free_voucher_proven":statuses["voucher_balance"]=="positive",
         "note":"Cash, voucher, and generic credits are not assumed interchangeable. Values are withheld."},
        ensure_ascii=False))
    print("MiniMax account balance query completed; no synthesis.")

if __name__=="__main__":
    try:main()
    except Exception as ex:
        print("MiniMax balance verification stopped:",type(ex).__name__)
        raise SystemExit(1)
