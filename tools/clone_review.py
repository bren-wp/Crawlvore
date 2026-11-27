"""Conservative structural clone candidates; not a semantic equivalence proof.

Scan Python runtime function statement windows with normalized identifiers and
constants. Exclude tests, tools, generated JavaScript and vendored dependencies.
"""
import ast
import collections
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
class Normalize(ast.NodeTransformer):
    def __init__(self):
        self.names={}
    def visit_Name(self,node):
        if node.id not in self.names: self.names[node.id]='v'+str(len(self.names))
        return ast.copy_location(ast.Name(id=self.names[node.id],ctx=node.ctx),node)
    def visit_Constant(self,node):
        return ast.copy_location(ast.Constant(value=type(node.value).__name__),node)

def report():
    groups=collections.defaultdict(list)
    functions=windows=0
    for path in sorted((ROOT/'src').glob('*.py')):
        tree=ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)): continue
            functions+=1
            for offset in range(max(0,len(node.body)-3)):
                statements=node.body[offset:offset+4]
                if sum(1 for item in statements for _ in ast.walk(item))<35: continue
                snippet=ast.Module(body=statements,type_ignores=[])
                copy=ast.parse(ast.unparse(snippet))
                key=ast.dump(Normalize().visit(copy),include_attributes=False)
                groups[key].append({'file':path.name,'function':node.name,'line':statements[0].lineno})
                windows+=1
    candidates=[items for items in groups.values() if len({(x['file'],x['function']) for x in items})>1]
    return {'scope':'src Python runtime and launcher; normalized four-statement windows; manual review required; no semantic equivalence proof','functions':functions,'windows':windows,'candidates':candidates}

if __name__=='__main__': print(json.dumps(report(),indent=2))
