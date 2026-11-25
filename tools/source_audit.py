"""Local, offline inventory and conservative AST candidate scan (not a vulnerability database)."""
import ast
import collections
import importlib.metadata as md
import json
from pathlib import Path
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
ROOT=Path(__file__).resolve().parents[1]

def dependencies():
    pending=[Requirement(s.strip()) for p in (ROOT/'requirements.txt',ROOT/'windows/requirements-build.txt') for s in p.read_text().splitlines() if s.strip() and not s.startswith('#')]
    seen={}; issues=[]
    while pending:
        req=pending.pop(); name=canonicalize_name(req.name)
        if req.marker and not req.marker.evaluate(): continue
        try: dist=md.distribution(req.name)
        except md.PackageNotFoundError:
            issues.append({'requirement':str(req),'issue':'not installed in this environment'}); continue
        if req.specifier and not req.specifier.contains(dist.version,prereleases=True): issues.append({'requirement':str(req),'installed':dist.version,'issue':'version mismatch'})
        if name in seen: continue
        seen[name]=dist.version
        pending.extend(Requirement(r) for r in dist.requires or [])
    return dict(sorted(seen.items())),issues

def run():
    unused=[]; clones=collections.defaultdict(list); review=[]; funcs=0
    for path in sorted(ROOT.glob('*.py')):
        tree=ast.parse(path.read_text()); used={n.id for n in ast.walk(tree) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Load)}
        for node in ast.walk(tree):
            if isinstance(node,(ast.Import,ast.ImportFrom)):
                for a in node.names:
                    name=a.asname or (a.name.split('.')[0] if isinstance(node,ast.Import) else a.name)
                    if name not in used and name!='*': unused.append({'file':path.name,'line':node.lineno,'name':name})
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
                funcs+=1; size=sum(1 for _ in ast.walk(node));
                if size>=25:
                    # Normalize local identifiers, but retain literals and attribute names to reduce false positives.
                    body=ast.Module(body=node.body,type_ignores=[])
                    class Norm(ast.NodeTransformer):
                        def __init__(self): self.names={}
                        def visit_Name(self,n):
                            if n.id not in self.names: self.names[n.id]=f'n{len(self.names)}'
                            return ast.copy_location(ast.Name(id=self.names[n.id],ctx=n.ctx),n)
                    key=ast.dump(Norm().visit(ast.parse(ast.unparse(body))),include_attributes=False)
                    clones[key].append(f'{path.name}:{node.lineno}:{node.name}')
            if isinstance(node,ast.Call):
                fn=ast.unparse(node.func)
                if fn in ('eval','exec','pickle.loads','os.system') or any(k.arg=='shell' and isinstance(k.value,ast.Constant) and k.value.value is True for k in node.keywords) or any(k.arg=='verify' and isinstance(k.value,ast.Constant) and k.value.value is False for k in node.keywords): review.append({'file':path.name,'line':node.lineno,'call':fn})
    deps,issues=dependencies()
    return {'functions_scanned':funcs,'unused_import_candidates':unused,'normalized_ast_clone_candidates':[v for v in clones.values() if len(v)>1],'high_risk_call_patterns':review,'installed_dependency_closure':deps,'dependency_resolution_issues':issues,'scope':'top-level runtime Python modules; lexical imports and normalized whole-function AST only; no CVE lookup or semantic equivalence proof'}
if __name__=='__main__': print(json.dumps(run(),indent=2))
