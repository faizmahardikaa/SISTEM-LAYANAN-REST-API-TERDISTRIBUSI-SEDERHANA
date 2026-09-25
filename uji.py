"""Uji terukur. Jalankan round-robin sebelum trafik lain lewat port 8080."""
import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

ROOT = Path(__file__).resolve().parent


def call(port, payload=None):
    body = None if payload is None else json.dumps(payload).encode()
    req = Request(f"http://127.0.0.1:{port}/api/data", data=body,
                  headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=8) as response:
        return response.status, json.load(response), response.headers.get("X-Upstream-Addr", "-")


def run(mode):
    lines = []

    def out(text):
        lines.append(text)
        print(text)

    out(f"$ python uji.py {mode}")
    out("Waktu UTC: " + datetime.now(timezone.utc).isoformat(timespec="seconds"))
    if mode == "shared":
        name = "Data-uji-" + datetime.now(timezone.utc).strftime("%H%M%S%f")
        status_a, a, _ = call(5001, {"name": name})
        status_b, b, _ = call(5002)
        item = next(row for row in b["data"] if row["id"] == a["data"]["id"])
        out(f"POST :5001/api/data | HTTP {status_a} | server={a['server_id']}")
        out(json.dumps(a["data"], ensure_ascii=False))
        out(f"GET  :5002/api/data | HTTP {status_b} | server={b['server_id']}")
        out(json.dumps(item, ensure_ascii=False))
        assert status_a == 201 and status_b == 200
        assert a["server_id"] == "A" and b["server_id"] == "B"
        assert item == a["data"] and item["created_by"] == "A"
        out("LULUS: ID, isi, pembuat, dan waktu data sama pada A dan B.")
    else:
        if mode == "failover":
            try:
                call(5001)
            except URLError:
                out("Cek langsung :5001 -> koneksi gagal (Server A mati).")
            else:
                raise AssertionError("Matikan Server A terlebih dahulu!")
        ids = []
        for i in range(1, 11):
            status, body, upstream = call(8080)
            ids.append(body["server_id"])
            out(f"{i:02d} | HTTP {status} | Server {body['server_id']} | port={body['port']} | upstream={upstream}")
            assert status == 200
        count = Counter(ids)
        out(f"Jumlah: A={count['A']}, B={count['B']}; sukses=10/10")
        if mode == "round-robin":
            assert count == {"A": 5, "B": 5}
            assert all(a != b for a, b in zip(ids, ids[1:]))
            out("LULUS: dua server bergantian melayani 10 request.")
        else:
            assert ids == ["B"] * 10
            out("LULUS: 10 request tetap berhasil melalui Server B.")
    (ROOT / "bukti").mkdir(exist_ok=True)
    (ROOT / "bukti" / f"{mode}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["round-robin", "shared", "failover"])
    run(parser.parse_args().mode)
