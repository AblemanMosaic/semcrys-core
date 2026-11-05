"""Read-only migration and release-disposition workbench."""
import hashlib
import json
from importlib.resources import files

from streaming_app.core import Refusal
from streaming_legend.core import canonical

FINAL_DISPOSITIONS={
 'QUALIFIED_CURRENT_CANDIDATE','OPTIONAL_RESEARCH_PRESERVED_NOT_RELEASE_BLOCKING',
 'HELD_TYPED_UNAVAILABLE_NO_SECURITY_FALLBACK','HELD_PROPOSAL_ONLY_NO_SOURCE_MUTATION',
 'SUPERSEDED_BY_CURRENT_ROOTED_CONTRACT_LEGACY_PARITY_NOT_CLAIMED',
 'PARTIAL_SUCCESSOR_EXPLICIT_LEGACY_PARITY_NOT_CLAIMED'}
ROW_FIELDS={'semantic_slug','kind','legacy_parameter_or_invariant','phase','planned_disposition','final_disposition',
 'historical_disposition_blocking','qualified_current_candidate','available_now','current_runtime','api_cli_status',
 'reason','evidence_refs','standing'}


def _validate(value):
    if type(value) is not dict or value.get('schema')!='semcrys.migration-status.v0.2':
        raise Refusal('HELD_MIGRATION_STATUS_SCHEMA')
    root=value.get('status_root')
    base={k:v for k,v in value.items() if k!='status_root'}
    if not isinstance(root,str) or root!=hashlib.sha256(canonical(base)).hexdigest():
        raise Refusal('HELD_MIGRATION_STATUS_ROOT')
    try:
        release_bytes=files('semcrys').joinpath('RELEASE_SCOPE.json').read_bytes()
    except OSError as exc:
        raise Refusal('HELD_MIGRATION_RELEASE_SCOPE_MISSING') from exc
    if hashlib.sha256(release_bytes).hexdigest()!=value.get('release_scope_sha256'):
        raise Refusal('HELD_MIGRATION_RELEASE_SCOPE_DRIFT')
    rows=value.get('rows')
    if not isinstance(rows,list) or len(rows)!=value.get('row_count'):
        raise Refusal('HELD_MIGRATION_STATUS_ROWS')
    slugs=[]
    for row in rows:
        if type(row) is not dict or set(row)!=ROW_FIELDS or row.get('standing')!='CANDIDATE_ONLY':
            raise Refusal('HELD_MIGRATION_STATUS_ROW_SCHEMA')
        if row.get('final_disposition') not in FINAL_DISPOSITIONS or type(row.get('historical_disposition_blocking')) is not bool or type(row.get('available_now')) is not bool:
            raise Refusal('HELD_MIGRATION_STATUS_ROW_SCHEMA')
        if not isinstance(row.get('evidence_refs'),list) or not all(isinstance(item,str) for item in row['evidence_refs']):
            raise Refusal('HELD_MIGRATION_STATUS_ROW_SCHEMA')
        slugs.append(row.get('semantic_slug'))
    if any(not isinstance(slug,str) or not slug for slug in slugs) or len(slugs)!=len(set(slugs)) or slugs!=sorted(slugs):
        raise Refusal('HELD_MIGRATION_STATUS_ROWS')
    counts={name:sum(row['final_disposition']==name for row in rows) for name in FINAL_DISPOSITIONS}
    if {k:v for k,v in counts.items() if v}!=value.get('disposition_counts'):
        raise Refusal('HELD_MIGRATION_STATUS_COUNTS')
    if value.get('historical_disposition_blocker_count')!=sum(row['historical_disposition_blocking'] for row in rows):
        raise Refusal('HELD_MIGRATION_STATUS_COUNTS')
    return value


def _load():
    try:
        value=json.loads(files('semcrys').joinpath('MIGRATION_STATUS.json').read_text(encoding='utf-8'))
    except (OSError,ValueError,UnicodeError,RecursionError) as exc:
        raise Refusal('HELD_MIGRATION_STATUS_MISSING_OR_INVALID') from exc
    return _validate(value)


def status(*,include_rows=False):
    value=_load()
    result={k:v for k,v in value.items() if k!='rows'}
    if include_rows:
        result['rows']=value['rows']
    result['operation']='READ_ONLY_STATUS'
    result['canonical_mutation']=False
    result['relationship_state_mutation']=False
    return result


def export():
    """Return the complete deterministic status artifact for caller publication."""
    return _load()
