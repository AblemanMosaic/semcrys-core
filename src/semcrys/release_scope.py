"""Explicit release-scope model synchronized with the installed command parser."""
import hashlib,json
from importlib.resources import files
from streaming_app.core import Refusal
from streaming_legend.core import canonical

REQUIREMENTS=('stable-container-and-legend-abi','conservative-configuration-selection',
 'streaming-and-bounded-resources','compatibility-and-corruption','full-application-profile-integration',
 'packaging-and-documentation','release-courts','candidate-and-security-boundaries')
def load(commands):
    try:
        value=json.loads(files('semcrys').joinpath('RELEASE_SCOPE.json').read_text(encoding='utf-8'))
        def require(condition):
            if not condition:raise Refusal('HELD_RELEASE_SCOPE_DRIFT')
        require(value['schema']=='semcrys.release-scope.v0.1' and value['standing']=='CANDIDATE_ONLY')
        require(value['release_ready'] is False and all(value[k]=='NONE' for k in ('admission_effect','authority_effect','security_claim')))
        req=value['release_requirements'];require([r['id'] for r in req]==list(REQUIREMENTS) and all(r['required'] is True for r in req))
        groups=value['command_groups'];require(set(groups)=={'READ_ONLY','FILE_PUBLICATION','DIRECTORY_PUBLICATION','EXPLICIT_RECOVERY'})
        rows=[(command,group) for group,names in groups.items() for command in names]
        require(len(rows)==len({x[0] for x in rows})==len(commands))
        actual={r['command']:r['effect'] for r in commands}
        require(set(actual)=={x[0] for x in rows})
        require(all(actual[command]==('READ_ONLY' if group=='READ_ONLY' else 'EXPLICIT_LOCAL_OUTPUT') for command,group in rows))
    except (KeyError,TypeError,AttributeError,OSError,ValueError):raise Refusal('HELD_RELEASE_SCOPE_DRIFT') from None
    value['scope_root']=hashlib.sha256(canonical(value)).hexdigest()
    return value
