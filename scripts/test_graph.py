
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

MERGE (a)-[:DEPENDS_ON {
    kind: 'oracle',
    source_url: 'https://chain.link/'
}]->(o)

MERGE (b)-[:DEPENDS_ON {
    kind: 'oracle',
    source_url: 'https://chain.link/'
}]->(o)
""")

res = g.query("""
MATCH (p:Protocol)-[r:DEPENDS_ON]->(o:Oracle)
RETURN p.name, type(r), o.name
""")

for row in res.result_set:
    print(row)
