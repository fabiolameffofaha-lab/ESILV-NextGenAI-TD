# TD 2 – Étape 2 (Paire B) : le faux consensus

*Section destinée à `reports/td2.md`. TD 2 du 18/11/2026, pack 2026-11-18-students-5.
Tout est hors ligne : aucun appel fournisseur, uniquement `traces-td1.csv`, `reference-td1.csv` et `data/boutique.sqlite` (ouverte en lecture seule).*

- Script : [`kit-td1/pair_b_wrong_consensus.py`](../kit-td1/pair_b_wrong_consensus.py) (`python pair_b_wrong_consensus.py`)
- Sortie complète : [`reports/evidence/td2-pair-b-output.txt`](evidence/td2-pair-b-output.txt)

## 1. Le cas retenu : C09 (vrai batch du TD 1, pas un exemple fourni)

| Champ | Valeur |
|---|---|
| Identifiant | **C09** (famille F2 : âge révolu à une date) |
| Question | CA HT en centimes des clients ayant **exactement 25 ans au 2026-09-26** (toutes leurs commandes) |
| Nature | **Réel** : nos traces TD 1 du 21/10/2026 (`nature = real`, dernière tentative de chaque modèle) |
| Valeur fausse partagée | **0** |
| Modèles d'accord sur la valeur fausse | `cohere/north-mini-code:free` (OpenRouter), `qwen/qwen3.8-27b` (Groq), `dots-studio/dots-3-note-preview:free` (OpenRouter) |
| Modèles corrects | `openai/gpt-oss-120b`, `openai/gpt-oss-20b` (Groq) : 487980 |
| Référence | **487980** (`reference-td1.csv`, recalculée par une méthode indépendante, voir §4) |

### Résultat du quorum déclaré

| Panel | Seuil | Votes | Décision | vs référence |
|---|---|---|---|---|
| Panel fixe `atelier-vote.py` : 120b, cohere, qwen | **2 sur 3** | 0 → 2 voix (cohere, qwen) ; 487980 → 1 voix (120b) | **consensus sur 0** | **FAUX** |
| Les cinq modèles du TD 1 | **3 sur 5** | 0 → 3 voix (cohere, qwen, dots) ; 487980 → 2 voix (120b, 20b) | **consensus sur 0** | **FAUX** |

Le faux consensus **gagne dans les deux configurations**. Le seul modèle juste du panel fixe (gpt-oss-120b) est mis en minorité, et passer à 3 sur 5 n'aide pas : dots, qui n'est pas dans le panel fixe, ajoute la troisième voix au 0.

Deuxième cas, plus faible : **C10** (âge au moment de la commande). cohere et dots renvoient tous les deux 0 (la référence est 558980). Ici le vote **s'abstient** : au 2 sur 3 le meilleur score est 1 voix (120b, cohere et qwen donnent trois valeurs différentes), et au 3 sur 5 on a 2 voix pour 558980 contre 2 pour 0. L'erreur partagée ne passe pas, mais le panel ne donne pas la bonne réponse non plus.

## 2. Cause dans le SQL : trois erreurs différentes, une seule valeur

Les trois requêtes ont été rejouées telles quelles depuis `traces-td1.csv` : elles renvoient toutes 0. Pour trouver la clause fautive, j'ai évalué chaque sous-clause séparément sur la jointure orders × customers × product (397 lignes) :

| Modèle | Clause fautive | Lignes gardées | Explication |
|---|---|---:|---|
| cohere | `CAST(SUBSTR(c.birth_date,1,4) AS INTEGER) - CASE … END = 25` | **0** | Il manque `2026 -`. L'expression vaut une **année de naissance** (de 1958 à 2006), jamais 25. Avec `2026 - …` on retrouve 68 lignes et **487980**. |
| qwen | `strftime('%m-%d', o.date) >= strftime('%m-%d', c.birth_date)` **AND** `strftime('%m-%d', o.date) < strftime('%m-%d', date(c.birth_date,'+26 years'))` | **0** (129 et 268 lignes prises séparément) | Ajouter 26 ans ne change pas le jour-mois, donc la fenêtre devient `md >= X AND md < X` : elle est vide. Deuxième erreur : il calcule l'âge à `o.date` au lieu de la date de référence 2026-09-26 (c'est la logique de C10, pas celle de C09). |
| dots | `birth = 2001-09-26` **AND** `o.date` le 2026-09-26 | **0** (6 lignes pour la seule condition sur la naissance) | Il utilise une **égalité sur un jour** au lieu d'une fenêtre de naissance d'un an. En plus, il ne garde que les commandes passées le jour de référence, et il n'y en a aucune dans la base. |

**Point clé :** il n'y a pas de bug commun. Les trois modèles se trompent pour des raisons différentes, et ils tombent sur la même valeur parce que **0 est la valeur par défaut de tout filtre vide** (`COALESCE(SUM(...), 0)`). Un vote compte des valeurs identiques, pas des raisonnements identiques. Sur une question d'âge, toute erreur qui donne un filtre trop restrictif « vote » donc pour 0. C'est le même mécanisme que DEMO-SQL-C11 (§5) et que C10.

## 3. Requête delta : les lignes derrière l'écart (0 contre 487980)

```sql
SELECT c.customer_id, c.birth_date,
       COUNT(DISTINCT o.order_id)                     AS n_orders,
       COALESCE(SUM(o.quantity_product * p.price), 0) AS revenue_cents
FROM customers c
LEFT JOIN orders  o ON o.customer_id = c.customer_id
LEFT JOIN product p ON p.product_id  = o.product_id
WHERE c.birth_date >  date('2026-09-26', '-26 years')   -- > 2000-09-26
  AND c.birth_date <= date('2026-09-26', '-25 years')   -- <= 2001-09-26
GROUP BY c.customer_id, c.birth_date
ORDER BY c.birth_date;
```

| client | naissance | commandes | CA (centimes) |
|---|---|---:|---:|
| C007 | 2000-11-30 | 6 | 118740 |
| C009 | 2001-03-10 | 5 | 61330 |
| C008 | 2001-05-15 | 7 | 99090 |
| C002 | 2001-09-24 | 3 | 25920 |
| C001 | 2001-09-25 | 8 | 135000 |
| C003 | 2001-09-26 | 4 | 47900 |
| **Total** | | | **487980** = référence ✅ |

Les trois prédicats fautifs gardent 0 ligne chacun, donc l'écart correspond exactement à ces six clients. Cas limites vérifiés : C003 (né le 2001-09-26) a 25 ans **le jour même**, il est donc inclus. C005 (né le 2000-09-26) a **26 ans** ce jour-là, il est donc exclu. Ce sont ces bornes qui séparent C09 de C08 et de C16.

## 4. Méthode de contrôle indépendante

1. **Recalcul sans SQL ni modèle** : un script Python lit `data/*.csv` et calcule l'âge avec `age = année(d) − année(n) − ((mois,jour)(d) < (mois,jour)(n))`. Résultat : **487980**, identique à la référence. La vérification ne dépend donc ni de SQLite ni d'un LLM.
2. **Garde-fou sur la valeur 0** : sur les familles F2/F2b, un résultat de 0 doit déclencher un `SELECT COUNT(*)` de la population filtrée. Si la population ciblée par la question n'est pas vide (ici 6 clients, 33 commandes), le 0 est rejeté. Ce contrôle déterministe aurait bloqué C09 et C10.
3. **Un autre panel n'est pas une garantie** : 2 sur 3 et 3 sur 5 se trompent tous les deux sur C09. Un panel avec 120b et 20b aurait donné la bonne réponse sur ce batch, mais c'est un choix fait après coup (20 questions seulement) et non une propriété générale. → Pour la règle de routage (Paire C) : **pas de quorum seul sur F2**. Il faut la référence déterministe ou le contrôle de population, surtout si le chiffre est montré au client ou sert à un paiement.

## 5. Cas fournis (séparés de nos comptages)

**DEMO-SQL-C11** (cas historique réel, pilote de septembre 2026, ce n'est **pas** notre batch). Rejoué sur `boutique.sqlite` :
- M1 `openai/gpt-oss-20b` : `WHERE c.birth_date = '2001-12-01'` → **0**. Une égalité sur un seul jour : aucun client n'est né ce jour-là.
- M2 `cohere/north-mini-code:free` : `'2026-12-01' >= c.birth_date AND '2027-12-01' <= c.birth_date` → **0**. Les deux conditions sont contradictoires (0 client).
- Requête delta (fenêtre `]2000-12-01 ; 2001-12-01]`) : C009, C008, C002, C001, C003, C006 → somme **446690** = `reference-td1.csv` C11 ✅.
- Dans nos propres traces, C11 n'est **pas** un faux consensus : seul 20b se trompe (322160), et les deux votes donnent 446690.

**DEMO-VOTE** (exemple synthétique, ce ne sont pas des sorties de modèle) : une vente le 2026-01-01 de 100 centimes. Avec `sale_date > '2026-01-01'` (deux propositions) on obtient 0, avec `>=` on obtient 100. Le vote 2 sur 3 sur `[0, 0, 100]` retient 0 : c'est faux, parce que la borne incluse a été traitée comme exclue.

## 6. Comptage des votes à la main (pour vérifier la méthode de la Paire A)

Dernière tentative de chaque modèle. Un `sql_invalid` (cohere C02) reste dans n mais ne vote pas. Les 429 de qwen (C16–C20) ont été relancés avec succès (tentative 2), c'est cette valeur qui est comptée.

| Q | 2 sur 3 (panel fixe) | 3 sur 5 |
|---|---|---|
| C01, C03–C07, C12–C14, C20 | consensus correct | consensus correct |
| C02 | 590320 (2) ✅ | abstention (2) : 20b et dots divergent, cohere est invalide |
| C08 | 605580 (2) ✅ | abstention (2) |
| **C09** | **0 (2) ❌** | **0 (3) ❌** |
| C10 | abstention (1) | abstention (2 contre 2) |
| C11 | 446690 (3) ✅ | 446690 (4) ✅ |
| C15 | abstention (1) | abstention (2) |
| C16 | 376740 (2) ✅ | 376740 (3) ✅ |
| C17 | abstention (1) | abstention (2) |
| C18 | 62480 (3) ✅ | 62480 (4) ✅ |
| C19 | abstention (1) | 1990 (3) ✅ : 20b et dots font passer l'abstention à un consensus |

Bilan : **2 sur 3 → 15 consensus justes, 1 faux (C09), 4 abstentions (C10, C15, C17, C19). 3 sur 5 → 14 justes, 1 faux (C09), 5 abstentions (C02, C08, C10, C15, C17)**. Passer à 3 sur 5 fait perdre C02 et C08 (ils passent en abstention), fait gagner C19, et ne corrige pas C09. **À comparer ligne par ligne avec la sortie de `vote_k_sur_n` de la Paire A.**

## 7. Limites

- 20 questions et un seul batch : le faux consensus sur C09 est un fait observé dans ces traces, pas un taux d'erreur général.
- Les traces ont été fusionnées entre les membres. qwen a eu des 429 sur C16–C20 et c'est la deuxième tentative qui est comptée.
- On compare des valeurs, pas des requêtes : deux requêtes différentes qui tombent sur la même valeur fausse sont indiscernables pour le vote.
