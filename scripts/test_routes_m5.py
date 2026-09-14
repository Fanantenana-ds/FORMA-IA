
import httpx
import json

BASE = "http://localhost:8000/api/v1/ia/formations"


def main():
    print("=" * 70)
    print("🧪 TEST ROUTES M5 — FastAPI")
    print("=" * 70)

    # 1. Health
    print("\n[1] GET /health")
    r = httpx.get(f"{BASE}/health", timeout=10)
    print(f"   Status : {r.status_code}")
    data = r.json()
    print(f"   Agents : {data.get('implemented_count')}/{data.get('total_agents')}")

    # 2. Liste des agents
    print("\n[2] GET /agents")
    r = httpx.get(f"{BASE}/agents", timeout=10)
    print(f"   Status : {r.status_code}")
    print(f"   Actifs : {r.json().get('active_count')}/{r.json().get('total')}")

    # 3. Generate forms (Agent 1)
    print("\n[3] POST /generate-forms (Agent 1)")
    payload = {
        "titre": "Introduction à l'IA",
        "domaine": "IA",
        "niveau_cible": "Intermédiaire",
        "date_debut": "2026-10-15",
        "date_fin": "2026-10-16",
        "lieu": "Antananarivo",
        "formateur": "Rakoto",
        "max_participants": 20,
        "public_cible": "Ministère de l'Éducation",
    }
    r = httpx.post(f"{BASE}/generate-forms", json=payload, timeout=180)
    print(f"   Status : {r.status_code}")
    if r.status_code == 200:
        d = r.json()
        print(f"   Durée  : {d.get('duration_seconds')}s")
        print(f"   Data.inscription.questions : {len(d['data']['inscription']['questions'])}")
        print(f"   Data.test_avant.questions  : {len(d['data']['test_avant']['questions'])}")
    else:
        print(f"   ❌ {r.text[:200]}")


if __name__ == "__main__":
    main()