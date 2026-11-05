"""Explicit artifact operations. SPDX-License-Identifier: Apache-2.0"""
import base64
import binascii
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from streaming_app.core import Refusal, _count_units, _select_local_legend, _snapshot, protect_outputs
from streaming_legend import LegendReader, write_legend
from streaming_legend.core import canonical, file_sha256, migrate_json_v01
from streaming_legend.crys_v2 import inspect_crys
from streaming_legend.glyph import registry as build_glyph_registry, load as load_glyph, alphabet_parameters
from streaming_legend import scratch_io as sio


def canonical_object(path, max_bytes=64*1024*1024):
    path=Path(path)
    if path.stat().st_size>max_bytes: raise Refusal('HELD_ARTIFACT_SIZE_LIMIT')
    with path.open('rb') as f: data=f.read(max_bytes+1)
    if len(data)>max_bytes: raise Refusal('HELD_ARTIFACT_SIZE_LIMIT')
    try:
        value=json.loads(data.decode('utf-8'))
        if type(value) is not dict or canonical(value)!=data: raise Refusal('HELD_NONCANONICAL_ARTIFACT')
    except (UnicodeError,ValueError,RecursionError) as exc:
        if isinstance(exc,Refusal): raise
        raise Refusal('HELD_INVALID_ARTIFACT_JSON') from exc
    return value


def migrate_json_legend(source,output,*,index_stride=256):
    source,output=Path(source),Path(output); protect_outputs([output],[source])
    result=migrate_json_v01(source,output,index_stride=index_stride)
    return {'status':'PASS','schema':'semcrys.legend-migration.v0.1','standing':'CANDIDATE_ONLY',
        'source_sha256':result['source_sha256'],'output_sha256':result['sha256'],'entry_count':result['entry_count'],'id_sequence_preserved':True,
        'source_format':'semcrys.legend.v0.1','output_format':'semcrys.legend.binary.v0.2'}


def build_legend(source,output,*,policy='TOTAL'):
    source,output=Path(source),Path(output); protect_outputs([output],[source])
    if policy not in ('TOTAL','PROFITABLE'): raise Refusal('HELD_LEGEND_POLICY_UNAVAILABLE')
    with sio.TempDirectory(prefix='semcrys-legend-build-') as name:
        work=Path(name); snapshot=work/'source'; root=_snapshot(source,snapshot)
        counts=_count_units(snapshot,work/'counts.sqlite3',max_unit_bytes=4096)
        result=_select_local_legend(work/'counts.sqlite3',output,policy=policy,base_lookup=None,parent_root=None)
    return {'status':'PASS','schema':'semcrys.legend-build.v0.1','standing':'CANDIDATE_ONLY','source_sha256':root,
        'output_sha256':result['sha256'],'entry_count':result['entry_count'],'count_stats':list(counts),
        'effective_configuration':{'tokenizer':'UNICODE_CATEGORY_LOSSLESS_V1','policy':policy,'max_unit_bytes':4096,'oversize':'LITERAL'}}


def extract_legend(source,output,*,binding_index):
    source,output=Path(source),Path(output); protect_outputs([output],[source])
    if output.suffix.lower()!='.leg': raise Refusal('HELD_LEG_SUFFIX_REQUIRED')
    if type(binding_index) is not int or binding_index<0: raise Refusal('HELD_BINDING_INDEX')
    output.parent.mkdir(parents=True,exist_ok=True)
    with sio.TempDirectory(prefix='semcrys-extract-',dir=output.parent) as name:
        snapshot=Path(name)/'source.crys';_snapshot(source,snapshot)
        inspection=inspect_crys(snapshot,capture_directory=Path(name))
        bindings=inspection['header']['legend_bindings']
        if binding_index>=len(bindings): raise Refusal('HELD_BINDING_INDEX')
        binding=bindings[binding_index]
        if binding['mode']!='EMBEDDED': raise Refusal('HELD_BINDING_IS_EXTERNAL')
        ordinal=sum(row['mode']=='EMBEDDED' for row in bindings[:binding_index])
        path=Path(inspection['embedded_paths'][ordinal])
        if file_sha256(path)!=binding['sha256']: raise Refusal('HELD_EXTRACTED_LEGEND_ROOT')
        sio.replace(path,output)
    return {'status':'PASS','schema':'semcrys.legend-extraction.v0.1','standing':'CANDIDATE_ONLY',
        'container_sha256':inspection['file_sha256'],'output_sha256':binding['sha256'],'binding_index':binding_index,'role':binding['role']}


def glyph_registry(glyphs,*,name):
    return build_glyph_registry(glyphs,name=name)


def build_glyph_artifact(source,output,*,glyphs,name):
    if source is not None:raise Refusal('HELD_GLYPH_BUILD_SOURCE')
    output=Path(output)
    if output.suffix.lower()!='.gly':raise Refusal('HELD_GLY_SUFFIX_REQUIRED')
    value=glyph_registry(list(glyphs),name=name);sio.write_bytes(output,canonical(value))
    return {'status':'PASS','schema':'semcrys.glyph-build.v0.1','standing':'CANDIDATE_ONLY',
      'output_sha256':file_sha256(output),'glyph_count':len(value['glyphs'])}


def inspect_glyph(path):
    value,_,root=load_glyph(path)
    available=value['kind']=='TEMPLATE' and len(value['glyphs'])>=2
    return {'status':'PASS','schema':'semcrys.glyph-inspection.v0.1','standing':'CANDIDATE_ONLY','sha256':root,
        'glyph_count':len(value['glyphs']),'kind':value['kind'],
        'glyph_output_integration':'EXPLICIT_TOKEN_PROJECTION_AVAILABLE' if available else 'NOT_QUALIFIED_FOR_TOKEN_PROJECTION'}


def export_glyphs(source,output,*,external_legends=(),glyph_registry=None,max_decoded_bytes=1<<40,max_container_bytes=1<<40):
    from streaming_app.core import decode_file,_capture_controls,_lzma_decompress
    source,output=Path(source),Path(output)
    protect_outputs([output],[source,*external_legends,*([glyph_registry] if glyph_registry is not None else [])])
    if source.stat().st_size>max_container_bytes: raise Refusal('HELD_CONTAINER_SIZE_LIMIT')
    output.parent.mkdir(parents=True,exist_ok=True)
    with sio.TempDirectory(prefix='semcrys-glyph-export-',dir=output.parent) as name:
        work=Path(name); snapshot=work/'input.crys'; root=_snapshot(source,snapshot)
        decoded=decode_file(snapshot,work/'check',external_legends=external_legends,glyph_registry=glyph_registry,
            max_decoded_bytes=max_decoded_bytes,max_container_bytes=max_container_bytes)
        inspection,body,_=_capture_controls(snapshot,work)
        config=inspection['configuration']
        if config.get('projection')!='GLYPH': raise Refusal('HELD_NOT_A_GLYPH_PROJECTION')
        if config['outer_codec']=='LZMA':
            physical=work/'glyph.text'; _lzma_decompress(body,physical,max_decoded_bytes=256*max_decoded_bytes+5)
        else: physical=body
        output_root=file_sha256(physical); size=physical.stat().st_size; sio.replace(physical,output)
    return {'status':'PASS','schema':'semcrys.glyph-export.v0.1','standing':'CANDIDATE_ONLY','container_sha256':root,
        'output_sha256':output_root,'bytes':size,'source_reconstruction_sha256':decoded['output_sha256'],
        'effective_configuration':config,'standalone_decode_without_constitution_and_legends':False}


def inspect_artifact(source):
    source=Path(source)
    if source.suffix.lower()=='.crys':
        result=inspect_crys(source)
        sections=result['sections']; total=source.stat().st_size
        body=sum(r['length'] for r in sections if r['type']=='BODY')
        legends=sum(r['length'] for r in sections if r['type']=='LEGD')
        payload=sum(r['length'] for r in sections)
        result['byte_accounting']={'container_bytes':total,'body_payload_bytes':body,
            'embedded_legend_payload_bytes':legends,'other_section_payload_bytes':payload-body-legends,
            'framing_header_manifest_bytes':total-payload,'universal_minimum_claimed':False}
        return result
    if source.suffix.lower()=='.leg':
        from streaming_legend import fold
        with source.open('rb') as handle: magic=handle.read(8)
        if magic==fold.MAGIC: return fold.inspect(source)
        from streaming_legend.assembly import ExecutionLegendReader
        reader=ExecutionLegendReader(source)
        if reader.is_assembly:
            from .assembly import inspect
            return inspect(source)
        return reader.verify()
    if source.suffix.lower()=='.gly': return inspect_glyph(source)
    raise Refusal('HELD_EXPLICIT_FORMAT_REQUIRED')
