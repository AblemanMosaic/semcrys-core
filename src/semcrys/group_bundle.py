"""Complete group-legend bundle envelope; no nested execution or security claim.

The physical schemas retain their historical ``semcrys.metalegend-*`` names as
immutable compatibility ABI.

SPDX-License-Identifier: Apache-2.0
"""
from streaming_legend import scratch_io as sio
from pathlib import Path
from streaming_legend.core import file_sha256
from streaming_legend.crys_v2 import inspect_crys,write_crys,Limits
from streaming_app.core import _lzma_compress,_lzma_decompress,Refusal
from . import group_auxiliary as aux
SCHEMA='semcrys.metalegend-bundle-instance.v0.1'
BODY_SCHEMA='semcrys.metalegend-bundle-body.v0.1'
MAX_INNER=320*1024*1024
OPERATIONS=['VERIFY_SELF_CONTAINED_META_ARCHIVE','COMPRESS_COMPLETE_INNER_ARCHIVE',
 'VERIFY_EXACT_INNER_BYTES','RESTORE_ORIGINAL_ARTIFACTS_AND_TEXT']
FIELDS=('schema','standing','profile','inner_archive_sha256','inner_archive_bytes','inner_configuration_sha256',
 'manifest_sha256','outer_codec','body_schema','operation_sequence','security_claim','implicit_fallback',
 'instance_constitution_sha256')
def fail(code): raise Refusal(code)
def wrap(source,target,compressed):
    from .group_legend import SCHEMA as INNER,validate,root
    view=inspect_crys(source,limits=Limits(max_section_bytes=MAX_INNER,max_total_payload_bytes=MAX_INNER))
    cfg=view['configuration']; validate(cfg,view['header'])
    if cfg['schema'] not in (INNER,aux.SCHEMA) or cfg['placement']!='EMBEDDED' or cfg['outer_codec']!='NONE':
        fail('HELD_BUNDLE_REQUIRES_EMBEDDED_UNCOMPRESSED_INNER')
    size=Path(source).stat().st_size
    if not 1<=size<=MAX_INNER: fail('HELD_BUNDLE_INNER_SIZE')
    v={'schema':aux.BUNDLE_SCHEMA if cfg['schema']==aux.SCHEMA else SCHEMA,'standing':'CANDIDATE_ONLY','profile':'B:METALEGEND_BUNDLE',
      'inner_archive_sha256':file_sha256(source),'inner_archive_bytes':size,
      'inner_configuration_sha256':cfg['instance_constitution_sha256'],'manifest_sha256':cfg['manifest_sha256'],
      'outer_codec':'LZMA','body_schema':BODY_SCHEMA,'operation_sequence':OPERATIONS,
      'security_claim':'NONE','implicit_fallback':False}
    v['instance_constitution_sha256']=root(v)
    _lzma_compress(Path(source),Path(compressed))
    write_crys(target,configuration=v,body=compressed,legend_stack=[],decoded_sha256=v['manifest_sha256'])
    return v
def unwrap_captured(view,body,target):
    from .group_legend import SCHEMA as INNER,validate,root,isroot
    v=view['configuration']; header=view['header']
    if type(v) is not dict or set(v)!=set(FIELDS): fail('HELD_BUNDLE_FIELDS')
    if v['schema'] not in (SCHEMA,aux.BUNDLE_SCHEMA) or v['standing']!='CANDIDATE_ONLY' or v['profile']!='B:METALEGEND_BUNDLE':
        fail('HELD_BUNDLE_SCHEMA')
    if v['outer_codec']!='LZMA' or v['body_schema']!=BODY_SCHEMA or v['operation_sequence']!=OPERATIONS:
        fail('HELD_BUNDLE_OPERATIONS')
    if v['security_claim']!='NONE' or v['implicit_fallback'] is not False: fail('HELD_BUNDLE_CLAIM')
    if header['legend_bindings'] or header['glyph_binding'] is not None: fail('HELD_BUNDLE_DEPENDENCIES')
    if type(v['inner_archive_bytes']) is not int or not 1<=v['inner_archive_bytes']<=MAX_INNER:
        fail('HELD_BUNDLE_INNER_SIZE')
    for field in ('inner_archive_sha256','inner_configuration_sha256','manifest_sha256','instance_constitution_sha256'):
        if not isroot(v[field]): fail('HELD_BUNDLE_ROOT')
    if header['decoded_sha256']!=v['manifest_sha256'] or root({k:x for k,x in v.items() if k!='instance_constitution_sha256'})!=v['instance_constitution_sha256']:
        fail('HELD_BUNDLE_ROOT')
    _lzma_decompress(Path(body),Path(target),max_decoded_bytes=v['inner_archive_bytes'])
    if Path(target).stat().st_size!=v['inner_archive_bytes'] or file_sha256(target)!=v['inner_archive_sha256']:
        fail('HELD_BUNDLE_INNER_ROOT')
    inner=inspect_crys(target,limits=Limits(max_section_bytes=MAX_INNER,max_total_payload_bytes=MAX_INNER))
    cfg=inner['configuration']
    expected_inner=aux.SCHEMA if v['schema']==aux.BUNDLE_SCHEMA else INNER
    if cfg.get('schema')!=expected_inner: fail('HELD_BUNDLE_RECURSIVE_OR_WRONG_INNER')
    validate(cfg,inner['header'])
    if cfg['placement']!='EMBEDDED' or cfg['outer_codec']!='NONE': fail('HELD_BUNDLE_INNER_LAYOUT')
    if cfg['manifest_sha256']!=v['manifest_sha256'] or cfg['instance_constitution_sha256']!=v['inner_configuration_sha256']:
        fail('HELD_BUNDLE_INNER_CORRESPONDENCE')
    return cfg
