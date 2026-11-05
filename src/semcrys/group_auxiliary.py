"""Typed group-legend auxiliaries, never semantic IDs or pooled token rows.

The physical schemas retain their historical ``semcrys.metalegend-*`` names as
immutable v0.1/v0.2 wire identifiers.

SPDX-License-Identifier: Apache-2.0
"""
import hashlib,json
from importlib.resources import files
from streaming_legend.core import canonical
from streaming_app.core import Refusal
SCHEMA='semcrys.metalegend-instance.v0.2'
BUNDLE_SCHEMA='semcrys.metalegend-bundle-instance.v0.2'
MANIFEST_SCHEMA='semcrys.restored-artifacts.v0.2'
KINDS=('GLYPH','FOLD');MAX_AUX=64;MAX_BYTES=64*1024*1024
def fail(code):raise Refusal('HELD_META_'+code)
def contract():
    v=json.loads(files('semcrys').joinpath('META_AUXILIARY_CONTRACT.json').read_text(encoding='utf-8'))
    expected={'archive_schema':SCHEMA,'bundle_schema':BUNDLE_SCHEMA,'manifest_schema':MANIFEST_SCHEMA,
        'auxiliary_kinds':list(KINDS),'maximum_auxiliaries':MAX_AUX,'maximum_auxiliary_bytes':MAX_BYTES,
        'resolution':'EXACT_KIND_AND_ROOT_FROM_SOURCE_CONFIGURATION','unused_or_duplicate_inputs':'REFUSE',
        'restoration':'EXACT_ARTIFACT_BYTES_THEN_REAL_SOURCE_DECODER','auxiliary_pooling':'VERBATIM_SPANS_NOT_LEGEND_RECORDS',
        'recursive_archives':'REFUSE'}
    if v.get('CM1')!=expected or v.get('standing')!='CANDIDATE_ONLY' or v.get('security_claim')!='NONE':fail('AUXILIARY_CONTRACT')
    return v
def contract_root():return hashlib.sha256(canonical(contract())).hexdigest()
def dependencies(view):
    required={}
    if type(view.get('configuration')) is not dict:fail('AUXILIARY_CONFIGURATION')
    g=view['header'].get('glyph_binding')
    f=view['configuration'].get('fold_projection')
    if (g is not None and type(g) is not dict) or (f is not None and type(f) is not dict):fail('AUXILIARY_BINDING')
    if any(v and v.get('mode')=='EXTERNAL' and 'sha256' not in v for v in (g,f)):fail('AUXILIARY_BINDING')
    if g and g.get('mode')=='EXTERNAL':required['GLYPH']=g['sha256']
    if f and f.get('mode')=='EXTERNAL':required['FOLD']=f['sha256']
    for digest in required.values():
        if type(digest) is not str or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):fail('AUXILIARY_ROOT')
    return required
def decoder_options(view,provided):
    required=dependencies(view);out={}
    for kind,digest in required.items():
        if (kind,digest) not in provided:fail('EXTERNAL_AUXILIARY_UNAVAILABLE')
        out['glyph_registry' if kind=='GLYPH' else 'fold_front']=provided[kind,digest]
    return out,required
