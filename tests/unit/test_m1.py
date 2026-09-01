# ============================================================
# test_m1.py — TEST M1 SANS BACKEND
# ============================================================
# Ce script teste votre API IA sans avoir besoin du Backend.
# Il appelle directement vos endpoints IA.
# ============================================================

import requests
import json

BASE_URL = "http://127.0.0.1:8000/api/v1"

def test_rechercher():
    """Test la recherche Tavily + analyse Groq"""
    url = f"{BASE_URL}/ia/veille/rechercher"
    
    # Requête de recherche
    data = {
        "query": "formation IA Madagascar stage data science",
        "domains": ["ia", "data"],
        "min_score": 60,
        "limit": 10
    }
    
    print("=" * 60)
    print("🔍 TEST M1 — RECHERCHE TAVILY + GROQ")
    print("=" * 60)
    print(f"📝 Requête: {data['query']}")
    print("-" * 60)
    
    try:
        response = requests.post(url, json=data, timeout=60)
        
        print(f"✅ Status HTTP: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get("success"):
                opportunities = result.get("data", {}).get("opportunities", [])
                total = result.get("data", {}).get("total", 0)
                validated = result.get("data", {}).get("validated_count", 0)
                
                print(f"✅ Success: True")
                print(f"✅ Total opportunités: {total}")
                print(f"✅ Validées: {validated}")
                print(f"✅ Rejetées/à revoir: {total - validated}")
                print("-" * 60)
                
                if opportunities:
                    print("\n📋 PREMIÈRES OPPORTUNITÉS :")
                    for i, opp in enumerate(opportunities[:3], 1):
                        print(f"\n{i}. {opp.get('title', 'Sans titre')}")
                        print(f"   Source: {opp.get('source', 'Non précisé')}")
                        print(f"   Domaine: {opp.get('domain', 'Non précisé')}")
                        print(f"   Score: {opp.get('score', 0)}%")
                        print(f"   Statut: {opp.get('status', 'inconnu')}")
                        if opp.get('summary'):
                            print(f"   Résumé: {opp.get('summary')[:150]}...")
                else:
                    print("\n⚠️ Aucune opportunité trouvée.")
                    print("   Vérifiez votre clé Tavily et votre connexion internet.")
            else:
                print(f"❌ Erreur: {result.get('error', 'Erreur inconnue')}")
        else:
            print(f"❌ Erreur HTTP: {response.status_code}")
            print(f"   Réponse: {response.text}")
            
    except requests.exceptions.Timeout:
        print("❌ Timeout: La requête a pris trop de temps")
    except requests.exceptions.ConnectionError:
        print("❌ Erreur de connexion: Vérifiez que le serveur tourne")
        print("   uvicorn app.main:app --reload --host 127.0.0.1 --port 8000")
    except Exception as e:
        print(f"❌ Erreur inattendue: {e}")
    
    print("\n" + "=" * 60)

def test_analyser_texte():
    """Test l'analyse de texte"""
    url = f"{BASE_URL}/ia/veille/analyser-texte"
    
    data = {
        "texte": """
        Le Ministère de la Santé recherche un prestataire pour former 
        50 agents à l'utilisation d'un système d'IA pour le diagnostic médical. 
        Budget estimé : 150 000 000 Ar. Date limite : 15/12/2026.
        """,
        "source": "manuel"
    }
    
    print("📝 TEST ANALYSE DE TEXTE")
    print("-" * 60)
    
    try:
        response = requests.post(url, json=data, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                total = result.get("data", {}).get("total", 0)
                print(f"✅ Analyse réussie: {total} opportunités")
            else:
                print(f"❌ Erreur: {result.get('error')}")
        else:
            print(f"❌ Erreur HTTP: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Erreur: {e}")

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🧪 TEST DU MODULE M1 — VEILLE MARCHÉ")
    print("=" * 60)
    print("⚠️ Assurez-vous que :")
    print("   1. Le serveur tourne (uvicorn app.main:app --reload)")
    print("   2. TAVILY_API_KEY est dans .env")
    print("   3. GROQ_API_KEY est dans .env")
    print("=" * 60 + "\n")
    
    test_rechercher()
    test_analyser_texte()