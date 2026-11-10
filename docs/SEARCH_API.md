# Product search API

`POST /search`, header `X-API-Key: myai_...`. The key determines the store;
there is no client-selectable tenant. Unknown request fields are rejected.
Search reads the current active catalog and requires no Qwen weights or adapter.

```json
{
  "query": "áo thun",
  "min_price": 100000,
  "max_price": 250000,
  "in_stock": true,
  "attributes": {"size": "L", "màu": "đen"},
  "limit": 6
}
```

All fields are optional. An empty query with filters searches by those filters.
An empty request returns no products. Prices are integer VND, bounds inclusive;
`min_price > max_price` is invalid. `in_stock: false` selects stock=0; null includes
both available and sold-out items. Attribute names/values ignore Vietnamese
accents and case; multiple values require all requested values. Missing attributes
do not match. Structured and natural-language constraints are intersected.

Response: `{"store_id":"...","products":[...],"count":1}`. Products include
id, store_id, name, price_vnd, stock, description, attributes, active. Limit 1–100.
401 means missing/revoked/invalid key; 422 means invalid input. No SQL is supplied
by the caller. Inactive items are excluded. Database changes appear next request.

Natural language supports keyword/SKU, explicit size/color, non-spicy food,
upper/lower/range price bounds (k/nghìn/ngàn/tr/triệu/VND), and availability.
It also accepts `ngân sách`, `không vượt quá`, ranges such as `300–360k`, and color
shades such as `đỏ đô`. V2.4 supports measurement equivalence (ml/L, g/kg, cm/m,
W/kW, decimal GB/TB), explicit quantity phrases and `còn sẵn`. Wireless queries
require radio-connection evidence in catalog attributes/name; unknown connections
do not qualify. Category synonyms and bounded spelling corrections are configured
in `myai/search_lexicon.json`, independently of SKU IDs or prices. Unmapped category
paraphrases remain a limitation; see [AUDIT_v2_4.md](../AUDIT_v2_4.md).
"X còn hàng không?" retains X even at zero stock so /chat can answer truthfully.
"X còn hàng" filters stock>0. General attribute filters use the `attributes` object;
this lexical baseline does not promise semantic interpretation of every phrase.

`POST /chat` retains its existing request/response. Model verification happens on
generation, so /search can be used before a model is installed. /health reports
whether model and adapter files exist; their existence is not inference readiness.
