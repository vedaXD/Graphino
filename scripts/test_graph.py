
from falkordb import FalkorDB

db = FalkorDB(host="localhost", port=6379)
g = db.select_graph("defi_risk")

g.query("""
MERGE (a:Protocol {slug: 'aave'})
SET a.name = 'Aave', a.category = 'Lending'

MERGE (b:Protocol {slug: 'compound'})
SET b.name = 'Compound', b.category = 'Lending'

MERGE (o:Oracle {oracle_id: 'chainlink'})
SET o.name = 'Chainlink'

MERGE (a)-[r1:DEPENDS_ON]->(o)
SET r1.kind = 'oracle',
    r1.source_url = 'https://chain.link/',
    r1.is_test = true,
    r1.risk_eligible = false,
    r1.verified = false

MERGE (b)-[r2:DEPENDS_ON]->(o)
SET r2.kind = 'oracle',
    r2.source_url = 'https://chain.link/',
    r2.is_test = true,
    r2.risk_eligible = false,
    r2.verified = false
""")

res = g.query("""
MATCH (p:Protocol)-[r:DEPENDS_ON]->(o:Oracle)
RETURN p.name, type(r), o.name
""")

for row in res.result_set:
    print(row)
