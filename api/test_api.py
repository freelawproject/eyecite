import requests

BASE = "http://localhost:8000"

def test_extract():
    resp = requests.post(f"{BASE}/extract", json={"text": "See 410 U.S. 113 (1973)."})
    assert resp.status_code == 200
    print("/extract:", resp.json())

def test_clean():
    resp = requests.post(f"{BASE}/clean", json={"text": "  See 410 U.S. 113 (1973).  "})
    assert resp.status_code == 200
    print("/clean:", resp.json())

if __name__ == "__main__":
    test_extract()
    test_clean()
