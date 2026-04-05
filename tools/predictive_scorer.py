"""
PredictiveScorer - Modelo de machine learning para prever probabilidade de fechamento.

Usa Logistic Regression implementada em numpy puro (sem sklearn) para funcionar
no Streamlit Cloud sem dependencias pesadas.

Features extraidas de cada escola:
- qualification_score (score IA base)
- n_contacts (numero de contatos encontrados)
- has_director_email (1 se tem email de diretor)
- n_emails_sent
- n_emails_opened
- n_emails_clicked
- n_emails_replied
- open_rate (0-1)
- reply_rate (0-1)
- days_since_first_contact
- school_size_num (0=pequena, 1=media, 2=grande, 3=mega)
- is_private (1 se privada)

Target (label positivo): escola respondeu email OR tem reuniao agendada/realizada

Modelo: Logistic Regression com gradient descent
- Peso inicial: heuristico (regras fixas atuais)
- Retreina semanalmente com dados acumulados
- Fallback para heuristica quando dados insuficientes (< 5 positivos)

Armazenamento: Pesos salvos em data/models/predictive_model.json
(simples, versionavel, sem pickle)

Usage:
    from tools.predictive_scorer import predictive_scorer

    # Treinar com dados atuais
    result = predictive_scorer.train()
    # {"trained": True, "samples": 89, "positives": 12, "accuracy": 0.78}

    # Prever score de uma escola
    score = predictive_scorer.predict_company(company_id)
    # {"probability": 0.73, "score": 73, "top_factors": [...], "method": "ml"}

    # Top N escolas com maior chance
    top = predictive_scorer.rank_companies(limit=10)
"""
import json
import math
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from database.supabase_client import db
from utils.logger import logger

MODEL_PATH = Path(__file__).parent.parent / "data" / "models" / "predictive_model.json"

# Feature order (ordem dos pesos deve coincidir)
FEATURES = [
    "qualification_score_norm",   # 0-1
    "n_contacts_norm",            # 0-1 (cap em 10)
    "has_director_email",         # 0/1
    "n_emails_sent_norm",         # 0-1 (cap em 5)
    "open_rate",                  # 0-1
    "reply_rate",                 # 0-1
    "click_rate",                 # 0-1
    "days_since_first_contact_norm",  # 0-1 (cap em 90 dias)
    "school_size_num",            # 0-3 normalizado /3
    "is_private",                 # 0/1
    "has_phone",                  # 0/1
]

# Pesos iniciais (heuristicos) — usados enquanto nao ha dados para treinar
INITIAL_WEIGHTS = {
    "qualification_score_norm": 1.5,
    "n_contacts_norm": 1.2,
    "has_director_email": 1.8,
    "n_emails_sent_norm": 0.3,
    "open_rate": 2.5,
    "reply_rate": 3.5,
    "click_rate": 2.0,
    "days_since_first_contact_norm": -0.5,
    "school_size_num": 0.8,
    "is_private": 0.6,
    "has_phone": 0.4,
}
INITIAL_BIAS = -2.0

SIZE_MAP = {
    "Ate 50": 0,
    "Entre 51 e 200": 0,
    "Entre 201 e 500": 1,
    "Entre 501 e 1000": 2,
    "Mais de 1000": 3,
}

FEATURE_LABELS_PT = {
    "qualification_score_norm": "Score de qualificacao IA",
    "n_contacts_norm": "Numero de contatos",
    "has_director_email": "Tem email do diretor",
    "n_emails_sent_norm": "Emails enviados",
    "open_rate": "Taxa de abertura",
    "reply_rate": "Taxa de resposta",
    "click_rate": "Taxa de cliques",
    "days_since_first_contact_norm": "Tempo desde 1o contato",
    "school_size_num": "Porte da escola",
    "is_private": "Privada",
    "has_phone": "Tem telefone",
}


def _sigmoid(x: float) -> float:
    """Sigmoid com clipping para evitar overflow."""
    if x < -500:
        return 0.0
    if x > 500:
        return 1.0
    return 1.0 / (1.0 + math.exp(-x))


class PredictiveScorer:
    """Modelo preditivo de fechamento de vendas."""

    def __init__(self) -> None:
        self.weights: Dict[str, float] = dict(INITIAL_WEIGHTS)
        self.bias: float = INITIAL_BIAS
        self.trained: bool = False
        self.last_training: Optional[str] = None
        self.n_samples: int = 0
        self.n_positives: int = 0
        self.accuracy: float = 0.0
        self._load()

    # ============================================================
    # PERSISTENCIA
    # ============================================================
    def _load(self) -> None:
        """Carrega pesos do modelo salvo (se existir)."""
        try:
            if MODEL_PATH.exists():
                with open(MODEL_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.weights = data.get("weights", INITIAL_WEIGHTS)
                self.bias = data.get("bias", INITIAL_BIAS)
                self.trained = data.get("trained", False)
                self.last_training = data.get("last_training")
                self.n_samples = data.get("n_samples", 0)
                self.n_positives = data.get("n_positives", 0)
                self.accuracy = data.get("accuracy", 0.0)
        except Exception as e:
            logger.warning(f"Erro ao carregar modelo preditivo: {e}")

    def _save(self) -> None:
        try:
            MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(MODEL_PATH, "w", encoding="utf-8") as f:
                json.dump({
                    "weights": self.weights,
                    "bias": self.bias,
                    "trained": self.trained,
                    "last_training": self.last_training,
                    "n_samples": self.n_samples,
                    "n_positives": self.n_positives,
                    "accuracy": self.accuracy,
                    "version": 1,
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Erro ao salvar modelo: {e}")

    # ============================================================
    # EXTRACAO DE FEATURES
    # ============================================================
    def _extract_features(
        self,
        company: Dict[str, Any],
        contacts: List[Dict[str, Any]],
        queue_items: List[Dict[str, Any]],
    ) -> Dict[str, float]:
        """Extrai vetor de features de uma escola com seus contatos e emails."""
        # Qualification score (0-100 -> 0-1)
        q_score = company.get("qualification_score") or 0
        qualification_score_norm = min(q_score / 100.0, 1.0)

        # Contatos
        n_contacts = len(contacts)
        n_contacts_norm = min(n_contacts / 10.0, 1.0)
        has_director_email = 1.0 if any(
            (c.get("decision_maker_type") == "diretor") and c.get("email")
            for c in contacts
        ) else 0.0

        # Emails
        sent = [q for q in queue_items if q.get("status") == "sent"]
        n_sent = len(sent)
        n_sent_norm = min(n_sent / 5.0, 1.0)
        n_opened = sum(1 for q in sent if q.get("opened_at"))
        n_clicked = sum(1 for q in sent if q.get("clicked_at"))
        n_replied = sum(1 for q in sent if q.get("replied_at"))

        open_rate = (n_opened / n_sent) if n_sent > 0 else 0.0
        click_rate = (n_clicked / n_sent) if n_sent > 0 else 0.0
        reply_rate = (n_replied / n_sent) if n_sent > 0 else 0.0

        # Tempo desde 1o contato
        days_since = 0.0
        if sent:
            first_sent = min((q.get("sent_at") or "9999") for q in sent)
            try:
                dt = datetime.fromisoformat(first_sent.replace("Z", "+00:00"))
                days_since = (datetime.now(timezone.utc) - dt).days
            except Exception:
                days_since = 0
        days_since_first_contact_norm = min(days_since / 90.0, 1.0)

        # Porte
        size_str = str(company.get("school_size") or "")
        size_num = 0
        for key, val in SIZE_MAP.items():
            if key.lower() in size_str.lower():
                size_num = val
                break

        # Tipo
        admin_cat = str(company.get("admin_category") or "").lower()
        is_private = 1.0 if "privad" in admin_cat else 0.0

        # Telefone
        has_phone = 1.0 if company.get("phone") else 0.0

        return {
            "qualification_score_norm": qualification_score_norm,
            "n_contacts_norm": n_contacts_norm,
            "has_director_email": has_director_email,
            "n_emails_sent_norm": n_sent_norm,
            "open_rate": open_rate,
            "reply_rate": reply_rate,
            "click_rate": click_rate,
            "days_since_first_contact_norm": days_since_first_contact_norm,
            "school_size_num": size_num / 3.0,
            "is_private": is_private,
            "has_phone": has_phone,
        }

    def _label_from_data(
        self,
        contacts: List[Dict[str, Any]],
        queue_items: List[Dict[str, Any]],
        meetings: List[Dict[str, Any]],
    ) -> int:
        """Define label positivo (1) ou negativo (0) para treino.
        Positivo = escola respondeu email OR tem reuniao marcada/realizada
        """
        # Resposta recebida
        for q in queue_items:
            if q.get("replied_at"):
                return 1
        # Reuniao marcada
        if meetings:
            return 1
        return 0

    def _score_from_features(self, features: Dict[str, float]) -> float:
        """Calcula probabilidade via logistic regression."""
        z = self.bias
        for name, weight in self.weights.items():
            z += weight * features.get(name, 0.0)
        return _sigmoid(z)

    # ============================================================
    # TREINO
    # ============================================================
    def _gather_training_data(self) -> Tuple[List[Dict[str, float]], List[int], List[str]]:
        """Busca todas as escolas e monta dataset (X, y, nomes)."""
        try:
            companies = db.client.table("companies").select("*").execute().data or []
            all_contacts = db.client.table("contacts").select("*").execute().data or []
            all_queue = db.client.table("approval_queue").select(
                "company_id,status,sent_at,opened_at,clicked_at,replied_at"
            ).execute().data or []
            try:
                all_meetings = db.client.table("meetings").select("company_id,status").execute().data or []
            except Exception:
                all_meetings = []
        except Exception as e:
            logger.error(f"Erro ao buscar dados de treino: {e}")
            return [], [], []

        # Agrupar por company_id
        contacts_by_cid: Dict[str, List[Dict]] = {}
        for c in all_contacts:
            contacts_by_cid.setdefault(c.get("company_id"), []).append(c)
        queue_by_cid: Dict[str, List[Dict]] = {}
        for q in all_queue:
            queue_by_cid.setdefault(q.get("company_id"), []).append(q)
        meetings_by_cid: Dict[str, List[Dict]] = {}
        for m in all_meetings:
            meetings_by_cid.setdefault(m.get("company_id"), []).append(m)

        X, y, names = [], [], []
        for comp in companies:
            cid = comp.get("id")
            cts = contacts_by_cid.get(cid, [])
            q_items = queue_by_cid.get(cid, [])
            meets = meetings_by_cid.get(cid, [])
            features = self._extract_features(comp, cts, q_items)
            label = self._label_from_data(cts, q_items, meets)
            X.append(features)
            y.append(label)
            names.append(comp.get("name", "?"))
        return X, y, names

    def train(
        self,
        learning_rate: float = 0.1,
        epochs: int = 500,
        l2: float = 0.01,
    ) -> Dict[str, Any]:
        """Treina o modelo via gradient descent em numpy puro.
        Retorna dict com stats do treino.
        """
        X, y, names = self._gather_training_data()
        n = len(X)
        if n < 10:
            return {
                "trained": False,
                "reason": f"Poucos dados ({n}). Precisa de pelo menos 10 escolas.",
                "samples": n,
            }

        positives = sum(y)
        negatives = n - positives
        if positives < 3:
            return {
                "trained": False,
                "reason": f"Poucos exemplos positivos ({positives}). Precisa de pelo menos 3 escolas que responderam ou agendaram reuniao.",
                "samples": n,
                "positives": positives,
                "fallback": "Usando pesos heuristicos ate ter mais dados.",
            }

        # Gradient descent
        weights = dict(INITIAL_WEIGHTS)
        bias = INITIAL_BIAS

        # Balancear classes (positivos sao raros)
        pos_weight = negatives / max(positives, 1)

        for epoch in range(epochs):
            # Forward pass
            predictions = []
            for features in X:
                z = bias
                for name, w in weights.items():
                    z += w * features.get(name, 0.0)
                predictions.append(_sigmoid(z))

            # Gradientes
            grad_b = 0.0
            grad_w: Dict[str, float] = {k: 0.0 for k in weights}
            for i in range(n):
                error = predictions[i] - y[i]
                # Peso maior para positivos (balanceamento)
                sample_weight = pos_weight if y[i] == 1 else 1.0
                grad_b += error * sample_weight
                for name in weights:
                    grad_w[name] += error * X[i].get(name, 0.0) * sample_weight

            # Update (com L2 regularization)
            bias -= learning_rate * (grad_b / n)
            for name in weights:
                weights[name] -= learning_rate * (grad_w[name] / n + l2 * weights[name])

        # Calcular accuracy
        correct = 0
        for i in range(n):
            z = bias
            for name, w in weights.items():
                z += w * X[i].get(name, 0.0)
            pred = 1 if _sigmoid(z) >= 0.5 else 0
            if pred == y[i]:
                correct += 1
        accuracy = correct / n

        # Salvar
        self.weights = weights
        self.bias = bias
        self.trained = True
        self.last_training = datetime.now(timezone.utc).isoformat()
        self.n_samples = n
        self.n_positives = positives
        self.accuracy = accuracy
        self._save()

        logger.info(
            "Modelo preditivo treinado",
            extra={"samples": n, "positives": positives, "accuracy": round(accuracy, 3)},
        )

        return {
            "trained": True,
            "samples": n,
            "positives": positives,
            "negatives": negatives,
            "accuracy": round(accuracy, 3),
            "top_features": self._top_features(5),
            "last_training": self.last_training,
        }

    def _top_features(self, n: int = 5) -> List[Dict[str, Any]]:
        """Retorna as N features mais importantes (por magnitude do peso)."""
        sorted_feats = sorted(self.weights.items(), key=lambda x: abs(x[1]), reverse=True)
        return [
            {
                "feature": FEATURE_LABELS_PT.get(name, name),
                "weight": round(w, 3),
                "impact": "positivo" if w > 0 else "negativo",
            }
            for name, w in sorted_feats[:n]
        ]

    # ============================================================
    # PREDICAO
    # ============================================================
    def predict_company(self, company_id: str) -> Dict[str, Any]:
        """Prediz probabilidade de fechamento para uma escola especifica."""
        try:
            comp = db.client.table("companies").select("*").eq("id", company_id).limit(1).execute().data
            if not comp:
                return {"erro": "Escola nao encontrada"}
            comp = comp[0]
            cts = db.client.table("contacts").select("*").eq("company_id", company_id).execute().data or []
            queue = db.client.table("approval_queue").select(
                "status,sent_at,opened_at,clicked_at,replied_at"
            ).eq("company_id", company_id).execute().data or []

            features = self._extract_features(comp, cts, queue)
            prob = self._score_from_features(features)

            # Fatores que mais contribuiram (peso * valor)
            contributions = []
            for name, w in self.weights.items():
                contrib = w * features.get(name, 0.0)
                contributions.append((name, contrib))
            contributions.sort(key=lambda x: abs(x[1]), reverse=True)
            top_factors = [
                {
                    "fator": FEATURE_LABELS_PT.get(n, n),
                    "impacto": round(c, 2),
                    "direcao": "+" if c > 0 else "-",
                }
                for n, c in contributions[:5]
            ]

            return {
                "nome": comp.get("name"),
                "probabilidade": round(prob, 3),
                "score": int(prob * 100),
                "fatores_top": top_factors,
                "metodo": "ml_trained" if self.trained else "heuristica",
            }
        except Exception as e:
            return {"erro": str(e)[:200]}

    def rank_companies(self, limit: int = 10, min_score: int = 0) -> Dict[str, Any]:
        """Ranking de escolas por probabilidade de fechamento."""
        try:
            companies = db.client.table("companies").select("*").execute().data or []
            all_contacts = db.client.table("contacts").select("*").execute().data or []
            all_queue = db.client.table("approval_queue").select(
                "company_id,status,sent_at,opened_at,clicked_at,replied_at"
            ).execute().data or []
        except Exception as e:
            return {"erro": str(e)[:200]}

        cts_by_cid: Dict[str, List] = {}
        for c in all_contacts:
            cts_by_cid.setdefault(c.get("company_id"), []).append(c)
        q_by_cid: Dict[str, List] = {}
        for q in all_queue:
            q_by_cid.setdefault(q.get("company_id"), []).append(q)

        scored = []
        for comp in companies:
            cid = comp.get("id")
            features = self._extract_features(comp, cts_by_cid.get(cid, []), q_by_cid.get(cid, []))
            prob = self._score_from_features(features)
            score = int(prob * 100)
            if score < min_score:
                continue
            scored.append({
                "id": cid,
                "nome": comp.get("name"),
                "cidade": comp.get("city"),
                "estado": comp.get("state"),
                "score_preditivo": score,
                "probabilidade": round(prob, 3),
                "score_qualificacao": comp.get("qualification_score"),
                "status": comp.get("status"),
            })

        scored.sort(key=lambda x: x["score_preditivo"], reverse=True)

        return {
            "total": len(scored),
            "top": scored[:limit],
            "metodo": "ml_trained" if self.trained else "heuristica",
            "modelo_info": {
                "treinado": self.trained,
                "amostras": self.n_samples,
                "positivos": self.n_positives,
                "accuracy": self.accuracy,
                "ultimo_treino": self.last_training,
            },
        }

    def model_info(self) -> Dict[str, Any]:
        """Retorna status atual do modelo."""
        return {
            "treinado": self.trained,
            "amostras": self.n_samples,
            "positivos": self.n_positives,
            "accuracy": round(self.accuracy, 3) if self.accuracy else 0,
            "ultimo_treino": self.last_training,
            "top_features": self._top_features(10),
            "bias": round(self.bias, 3),
        }


predictive_scorer = PredictiveScorer()
