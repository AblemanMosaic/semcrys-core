"""Public SemCrys CLI. SPDX-License-Identifier: Apache-2.0"""
import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

from . import __version__
from semcrys_core import __version__ as public_version
from .progress import emit as emit_progress
from . import application
from . import directory_application
from .artifacts import build_legend, extract_legend, glyph_registry, inspect_artifact, migrate_json_legend, export_glyphs
from .integrity import catalogue, verify_self
from .transaction import publish
from .recovery import inspect as recovery_inspect,rollback as recovery_rollback
from . import directory_recovery
from .library import build_library, select, encode_selected
from .ordered_import import import_ordered
from .batch import encode_batch
from .capabilities import surface
from .formats import registry as format_registry
from .archaic import registry as archaic_registry,compile_plan as compile_archaic_plan
from .transport import (PATHWAYS as TRANSPORT_PATHWAYS,CODECS as TRANSPORT_CODECS,PROJECTIONS as TRANSPORT_PROJECTIONS,
    capabilities as transport_capabilities,load_peer,negotiate as negotiate_transport,compile_frame,load_frame,verify_frame)
from .gtk_analysis import (analyze as analyze_gtk,capabilities as gtk_capabilities,
    export_vocabulary,verify_vocabulary)
from .workbench import status as workbench_status,export as workbench_export
from .codec_selection import DEFAULT_CODECS
from streaming_app.fold_projection import build_front,extract_front,prefix_front
from .archive import select_archive,encode_selected_archive
from .fold_provenance import compact_front,audit_front,restore_rich,delivery_cost
from .assembly import build as build_assembly,expand as expand_assembly,inspect as inspect_assembly
from .local_assembly import encode as encode_local_assembly
from .longitudinal_assembly import encode as encode_longitudinal_assembly
from .second_pass import transform as second_pass
from .group_legend import pack as pack_meta,unpack as unpack_meta
from .metalegend import (SeekableMetalegendReader,
    build as build_recursive_meta, restore as restore_recursive_meta,
    inspect as inspect_recursive_meta, verify as verify_recursive_meta)
from .synchronization import account_artifacts as sync_account, composition_proposal as sync_compose, disclosure as sync_disclosure, ordering_projection as sync_ordering
from . import standard_archive
from . import protected_artifact
from streaming_app import compile_funnel,decode_file,encode_file
from streaming_app.core import Refusal,protect_outputs,REQUESTABLE_OUTER_CODECS
from streaming_legend.core import canonical,file_sha256

def _publication_options(parser):
    parser.add_argument('--receipt',type=Path)
    parser.add_argument('--replace',action='store_true',help='explicitly replace existing output/receipt')

def _artifact_resource_options(parser):
    parser.add_argument('--max-scratch-bytes',type=int,default=4*1024**3,
        help='Legend/glyph/library realization scratch + native capacity, then output/receipt/backups/journal; not RAM')

def _composite_resource_options(parser):
    parser.add_argument('--max-scratch-bytes',type=int,default=4*1024**3,
        help='Shared composite logical scratch/native capacity and applicable file or directory publication costs; not RAM')

def _standard_cache_root():
    base=Path(os.environ.get('LOCALAPPDATA') or (Path.home()/'.cache'))
    return base/'Ableman Mosaic'/'SemCrys'/'cache'/'standard-v1'

def _secure_key(args, *, old=False):
    prefix='old_' if old else ''
    key_file=getattr(args,prefix+'key_file',None)
    if key_file is not None:return key_file.read_bytes()
    env_name=getattr(args,prefix+'key_env',None)
    value=os.environ.get(env_name) if env_name else None
    if value is None:raise Refusal('HELD_RUNTIME_KEY_ENV_MISSING')
    return value.encode('utf-8')

def parser():
    p=argparse.ArgumentParser(prog='semcrys',
        description='Pack files or folders into byte-exact, integerized .crys archives. Encoding is not encryption.',
        epilog='Quick start: semcrys PATH [PATH ...] -o ARCHIVE.crys. Use explain-default for the rooted policy and --help-json for agents.')
    p.add_argument('--version',action='version',
        version=f'SemCrys {public_version} (Full compiler {__version__}) Apache-2.0')
    p.add_argument('--help-json',action='store_true',help='emit the machine-readable CLI contract (may be used without a command)')
    p.add_argument('--progress',choices=('human','full','summary','quiet'),default='human',
        help='stderr progress: human text, full JSONL, compact JSONL, or quiet (place before command)')
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('verify-self'); sub.add_parser('profiles'); sub.add_parser('capabilities'); sub.add_parser('formats')
    c=sub.add_parser('pack',help='Recommended automatic file/folder to .crys workflow',
        description='Pack one or more files/folders. The default fully integerizes eligible UTF-8, measures exact codec candidates, deduplicates chunks, courts profitable local/cross-document composition, pools related legends, verifies replay, then publishes atomically.')
    c.add_argument('inputs',nargs='+',type=Path);c.add_argument('-o','--output',type=Path)
    c.add_argument('--mode',choices=['semantic','smallest','portable'],default='semantic',
        help='semantic (default): full eligible local integerization; smallest: permit semantic degradation when raw wins; portable: self-contained semantic alias')
    c.add_argument('--registry',type=Path,help='Optional caller-supplied semantic registry; does not grant canonical identity')
    cache_group=c.add_mutually_exclusive_group()
    cache_group.add_argument('--cache-root',type=Path,help='verified resumable chunk cache (default: per-user local application data)')
    cache_group.add_argument('--no-cache',action='store_true',help='disable resumable verified chunk caching')
    c.add_argument('--workers',type=int,default=0,help='parallel encoding workers; 0 selects up to four')
    c.add_argument('--chunk-bytes',type=int,default=standard_archive.DEFAULT_CHUNK_BYTES,
        help='maximum logical chunk bytes (1..67108864; default 33554432)')
    c.add_argument('--composition',choices=['auto','off'],default='auto',
        help='auto (default): admit profitable local/cross-document composition; off: advanced ablation')
    c.add_argument('--dry-run',action='store_true',help='inventory and report the plan without encoding or writing output')
    c=sub.add_parser('unpack',help='Restore a Standard .crys archive to a new directory')
    c.add_argument('source',type=Path);c.add_argument('output',type=Path);c.add_argument('--only',action='append',default=[])
    c.add_argument('--max-output-bytes',type=int,default=standard_archive.MAX_TOTAL_BYTES)
    c=sub.add_parser('list',help='List paths in a Standard .crys archive');c.add_argument('source',type=Path)
    c=sub.add_parser('verify',help='Prove manifest integrity and byte-exact reconstruction')
    c.add_argument('source',type=Path);c.add_argument('--max-output-bytes',type=int,default=standard_archive.MAX_TOTAL_BYTES)
    c=sub.add_parser('search',help='Search an embedded caller-registry Global Term Index')
    c.add_argument('source',type=Path);c.add_argument('query')
    sub.add_parser('explain-default',help='Emit the rooted Standard profile contract')
    sub.add_parser('help-json',help='Emit the installed machine-readable CLI contract')
    security=sub.add_parser('security',help='Protect complete group legends, indexes, legends, or metalegends with authenticated encryption').add_subparsers(dest='action',required=True)
    c=security.add_parser('protect');c.add_argument('source',type=Path);c.add_argument('output',type=Path)
    c.add_argument('--role',choices=protected_artifact.ROLES,required=True)
    c.add_argument('--padding',choices=protected_artifact.PADDING_POLICIES,default=protected_artifact.PADDING_POWER_OF_TWO)
    c.add_argument('--padding-bucket',type=int);c.add_argument('--key-file',type=Path);c.add_argument('--key-env',default='SEMCRYS_SECURE_KEY')
    c=security.add_parser('unprotect');c.add_argument('source',type=Path);c.add_argument('output',type=Path)
    c.add_argument('--key-file',type=Path);c.add_argument('--key-env',default='SEMCRYS_SECURE_KEY')
    c=security.add_parser('verify');c.add_argument('source',type=Path)
    c.add_argument('--key-file',type=Path);c.add_argument('--key-env',default='SEMCRYS_SECURE_KEY')
    c=security.add_parser('inspect');c.add_argument('source',type=Path)
    c=security.add_parser('rotate-key');c.add_argument('source',type=Path);c.add_argument('output',type=Path)
    c.add_argument('--old-key-file',type=Path);c.add_argument('--old-key-env',default='SEMCRYS_OLD_SECURE_KEY')
    c.add_argument('--key-file',type=Path);c.add_argument('--key-env',default='SEMCRYS_NEW_SECURE_KEY')
    group=sub.add_parser('synchronize',help='Read-only shared event-model measurement; never rewrites legends or containers').add_subparsers(dest='action',required=True)
    c=group.add_parser('disclosure'); c.add_argument('source',type=Path); c.add_argument('legend',type=Path); c.add_argument('--max-entries',type=int,default=5000000)
    c=group.add_parser('ordering'); c.add_argument('source',type=Path); c.add_argument('legend',type=Path); c.add_argument('--max-entries',type=int,default=5000000)
    c=group.add_parser('compose'); c.add_argument('source',type=Path); c.add_argument('legend',type=Path); c.add_argument('--minimum-count',type=int,default=3); c.add_argument('--max-entries',type=int,default=5000000)
    c=group.add_parser('account'); c.add_argument('--source',type=Path,action='append',required=True); c.add_argument('--container',type=Path,action='append',required=True); c.add_argument('--legend',type=Path,action='append',default=[])
    group=sub.add_parser('workbench',help='Read-only migration and release-disposition inspection').add_subparsers(dest='action',required=True)
    c=group.add_parser('status');c.add_argument('--rows',action='store_true',help='include all legacy disposition rows')
    group.add_parser('export')
    group=sub.add_parser('archaic',help='SemCrys-A role/profile compiler; no security claim').add_subparsers(dest='action',required=True)
    group.add_parser('profiles')
    c=group.add_parser('plan');c.add_argument('source',type=Path)
    c.add_argument('--role',required=True,choices=['SELF_CONTAINED_MANUAL','PENPAL_LONGITUDINAL','GUILD_PRESHARED','HYBRID_GUILD_LONGITUDINAL'])
    c.add_argument('--legend',type=Path,action='append',default=[])
    c.add_argument('--outer-codec',choices=REQUESTABLE_OUTER_CODECS,default='NONE')
    c.add_argument('--legend-policy',choices=['TOTAL','PROFITABLE'])
    c.add_argument('--projection',choices=['PACKED','INTEGER','GLYPH'],default='PACKED')
    c.add_argument('--glyph',type=Path);c.add_argument('--glyph-placement',choices=['EMBEDDED','EXTERNAL'],default='EMBEDDED')
    c.add_argument('--meaning-mode',choices=['SURFACE','GCNL_SENSE'],default='SURFACE')
    c.add_argument('--shuffle-mode',choices=['NONE','KEYED_LOCAL_ID_SHUFFLE'],default='NONE')
    group=sub.add_parser('transport',help='Transport-independent control-plane compiler; no network or cryptography').add_subparsers(dest='action',required=True)
    group.add_parser('capabilities')
    c=group.add_parser('negotiate');c.add_argument('local',type=Path);c.add_argument('remote',type=Path)
    c.add_argument('--pathway',required=True,choices=TRANSPORT_PATHWAYS)
    c.add_argument('--codec',required=True,choices=TRANSPORT_CODECS)
    c.add_argument('--projection',required=True,choices=TRANSPORT_PROJECTIONS)
    legends=c.add_mutually_exclusive_group(required=True)
    legends.add_argument('--legend-root',action='append',default=[]);legends.add_argument('--self-contained',action='store_true')
    c.add_argument('--security-mode',default='NONE')
    c=group.add_parser('frame');c.add_argument('body',type=Path);c.add_argument('negotiation',type=Path)
    c=group.add_parser('verify-frame');c.add_argument('frame',type=Path);c.add_argument('body',type=Path);c.add_argument('negotiation',type=Path)
    group=sub.add_parser('gtk',help='Read-only candidate GTK analysis; never mutates source or canonical CSIL/GTK').add_subparsers(dest='action',required=True)
    group.add_parser('capabilities')
    c=group.add_parser('analyze');c.add_argument('source',type=Path)
    c.add_argument('--schema-contract',required=True,type=Path)
    c.add_argument('--dossier',required=True,action='append',type=Path)
    c.add_argument('--decisions',type=Path)
    c.add_argument('--legend',action='append',default=[],type=Path)
    c.add_argument('--pathway',choices=['NL','GCNL'],default='NL')
    c.add_argument('--sense-binding',choices=['NONE','SENSE_KEYED'],default='NONE')
    c.add_argument('--sense-unresolved',choices=['HOLD','SPINE'],default='HOLD')
    c.add_argument('--force-csil',choices=['OFF','FLAG','HOLD'],default='FLAG')
    c.add_argument('--annotate',choices=['OFF','ON'],default='ON')
    c.add_argument('--max-source-bytes',type=int,default=64*1024*1024)
    c.add_argument('--max-legend-bytes',type=int,default=1024*1024*1024)
    c.add_argument('--max-units',type=int,default=1_000_000)
    c.add_argument('--max-annotations',type=int,default=100_000)
    c=group.add_parser('vocabulary');c.add_argument('output',type=Path)
    c.add_argument('--legend',action='append',required=True,type=Path)
    c.add_argument('--acknowledge-legend-disclosure',action='store_true')
    c.add_argument('--max-legend-bytes',type=int,default=1024*1024*1024)
    _publication_options(c);_artifact_resource_options(c)
    c=group.add_parser('verify-vocabulary');c.add_argument('source',type=Path)
    c.add_argument('--legend',action='append',required=True,type=Path)
    c.add_argument('--max-legend-bytes',type=int,default=1024*1024*1024)
    group=sub.add_parser('legacy').add_subparsers(dest='action',required=True)
    c=group.add_parser('import');c.add_argument('source',type=Path);c.add_argument('output',type=Path)
    c.add_argument('--format',required=True,choices=['SC_TEXT','SC_PACKED'])
    c.add_argument('--expected-source-sha256',required=True)
    c.add_argument('--legacy-legend',type=Path);c.add_argument('--legacy-glyph',type=Path)
    c.add_argument('--profile',choices=['C:RAW_BYTES','C:SELF_CONTAINED_TOKEN','T:PRESHARED_TOKEN','A:LONGITUDINAL_TOKEN_DELTA'],default='C:SELF_CONTAINED_TOKEN')
    c.add_argument('--legend',type=Path,action='append',default=[])
    c.add_argument('--outer-codec',choices=['NONE','LZMA'],default='NONE')
    c.add_argument('--legend-policy',choices=['TOTAL','PROFITABLE'])
    c.add_argument('--max-source-bytes',type=int,default=64*1024*1024)
    c.add_argument('--max-decoded-bytes',type=int,default=128*1024*1024)
    _publication_options(c);_composite_resource_options(c)
    group=sub.add_parser('recovery').add_subparsers(dest='action',required=True)
    c=group.add_parser('inspect');c.add_argument('journal',type=Path)
    c.add_argument('--expected-journal-root')
    c=group.add_parser('rollback');c.add_argument('journal',type=Path)
    c.add_argument('--output',type=Path,required=True);c.add_argument('--receipt',type=Path)
    c.add_argument('--expected-journal-root',required=True)
    c=group.add_parser('directory-inspect');c.add_argument('journal',type=Path)
    c.add_argument('--expected-journal-root')
    c=group.add_parser('directory-quarantine');c.add_argument('journal',type=Path)
    c.add_argument('--output',type=Path,required=True);c.add_argument('--expected-journal-root',required=True)
    def group_legend_commands(command, help_text):
        group=sub.add_parser(command,help=help_text).add_subparsers(dest='action',required=True)
        c=group.add_parser('pack'); c.add_argument('output',type=Path)
        c.add_argument('--source',type=Path,action='append',required=True)
        c.add_argument('--legend',type=Path,action='append',default=[])
        c.add_argument('--placement',choices=['EMBEDDED','EXTERNAL','AUTO'],default='EMBEDDED')
        c.add_argument('--layout',choices=['BODY_ONLY','WHOLE_BUNDLE','AUTO'],default='BODY_ONLY')
        c.add_argument('--accounting',choices=['COLD','WARM'],default='COLD')
        c.add_argument('--receiver-root',action='append',default=[])
        c.add_argument('--shared-pool',type=Path)
        c.add_argument('--glyph',dest='glyphs',type=Path,action='append',default=[],help='Exact external glyph registry required by source containers')
        c.add_argument('--fold-front',dest='fold_fronts',type=Path,action='append',default=[],help='Exact external folded projection required by source containers')
        c.add_argument('--selection',choices=['MIN_TOTAL','META','VERBATIM'],default='MIN_TOTAL')
        c.add_argument('--outer-codec',choices=['NONE','LZMA','AUTO'],default='AUTO')
        c.add_argument('--max-input-bytes',type=int,default=64*1024*1024)
        c.add_argument('--max-scratch-bytes',type=int,default=4*1024**3,help='Aggregate logical scratch bytes plus reserved SQLite capacity; not an RSS limit')
        c=group.add_parser('unpack'); c.add_argument('source',type=Path); c.add_argument('output',type=Path)
        c.add_argument('--meta',type=Path); c.add_argument('--max-output-bytes',type=int,default=128*1024*1024)
        c.add_argument('--max-scratch-bytes',type=int,default=4*1024**3,help='Aggregate logical scratch bytes plus reserved SQLite capacity; not an RSS limit')
        return group
    group_legend_commands('group-legend','Pool exact legend records across a related artifact group')
    group=group_legend_commands('metalegend','Recursive legend-of-a-legend operations; pack/unpack are v0.1 group-legend compatibility aliases')
    c=group.add_parser('build',help='Build a one-level recursive .mleg from a logical .leg')
    c.add_argument('source',type=Path); c.add_argument('output',type=Path)
    c.add_argument('--block-entries',type=int,default=4096)
    c.add_argument('--layout',choices=['seekable','whole'],default='seekable',
        help='seekable frames support targeted integer lookup; whole is the compact v0.1 control')
    c.add_argument('--frame-blocks',type=int,default=16,
        help='recipe blocks per independently compressed frame (seekable layout only)')
    c.add_argument('--allow-expansion',action='store_true',help='research only: publish even when .mleg is not smaller than .leg')
    c=group.add_parser('restore',help='Restore the byte-exact original .leg from a recursive .mleg')
    c.add_argument('source',type=Path); c.add_argument('output',type=Path)
    c=group.add_parser('inspect',help='Inspect and verify the recursive container envelope')
    c.add_argument('source',type=Path)
    c.add_argument('--fast',action='store_true',help='seekable layout only: validate the rooted directory without inflating every frame')
    c=group.add_parser('verify',help='Perform a full exact inverse without retaining the restored legend')
    c.add_argument('source',type=Path)
    c=group.add_parser('lookup',help='Resolve one or more legend integer IDs directly from a seekable metalegend')
    c.add_argument('source',type=Path); c.add_argument('identifier',type=int,nargs='+')
    c.add_argument('--cache-root',type=Path)
    c.add_argument('--cache-profile',choices=['COMPACT','BALANCED','THROUGHPUT'],default='BALANCED')
    c=group.add_parser('prepare',help='Materialize and verify the exact full legend in the local acceleration cache')
    c.add_argument('source',type=Path); c.add_argument('--cache-root',type=Path,required=True)
    c.add_argument('--cache-profile',choices=['COMPACT','BALANCED','THROUGHPUT'],default='BALANCED')
    c=sub.add_parser('second-pass'); c.add_argument('source',type=Path); c.add_argument('output',type=Path)
    c.add_argument('--legend',type=Path,action='append',default=[])
    c.add_argument('--selection',choices=['MIN_DELIVERY','MIN_DISPERSION','IDENTITY','ALL','TOP3','TOPK'],default='MIN_DELIVERY')
    c.add_argument('--accounting',choices=['COLD','WARM'],default='COLD')
    c.add_argument('--rounds',type=int,default=400); c.add_argument('--min-count',type=int,default=10)
    c.add_argument('--hot-k',type=int,default=3,help='Initial-frequency hot-set size; 3 preserves the frozen TOP3 profile')
    c.add_argument('--max-source-bytes',type=int,default=64*1024*1024); c.add_argument('--max-events',type=int,default=1_000_000)
    c.add_argument('--max-scratch-bytes',type=int,default=4*1024**3,help='Second-pass logical scratch/native capacity, then staged output + receipt + replacement backups under the same limit; excludes RAM and filesystem overhead')
    _publication_options(c)
    group=sub.add_parser('assembly').add_subparsers(dest='action',required=True)
    c=group.add_parser('encode'); c.add_argument('source',type=Path); c.add_argument('output',type=Path); c.add_argument('--rules',type=Path,required=True)
    c.add_argument('--outer-codec',choices=['NONE','LZMA'],default='NONE'); c.add_argument('--legend-policy',choices=['TOTAL','PROFITABLE'],default='PROFITABLE')
    c.add_argument('--encoding',choices=['TAGGED','COMPACT'],default='COMPACT'); c.add_argument('--policy',choices=['ALL','SHORTER'],default='SHORTER')
    c.add_argument('--selection',choices=['MIN_CONTAINER','ASSEMBLY'],default='MIN_CONTAINER'); c.add_argument('--max-source-bytes',type=int,default=64*1024*1024)
    _publication_options(c); _composite_resource_options(c)
    c=group.add_parser('encode-longitudinal'); c.add_argument('source',type=Path); c.add_argument('output',type=Path)
    c.add_argument('--rules',type=Path,required=True); c.add_argument('--legend',type=Path,action='append',required=True)
    c.add_argument('--outer-codec',choices=['NONE','LZMA'],default='NONE')
    c.add_argument('--encoding',choices=['TAGGED','COMPACT'],default='COMPACT'); c.add_argument('--policy',choices=['ALL','SHORTER'],default='SHORTER')
    c.add_argument('--selection',choices=['MIN_CONTAINER','ASSEMBLY'],default='MIN_CONTAINER')
    c.add_argument('--max-source-bytes',type=int,default=64*1024*1024); c.add_argument('--max-legend-bytes',type=int,default=1024*1024*1024)
    _publication_options(c); _composite_resource_options(c)
    c=group.add_parser('build-delta'); c.add_argument('source',type=Path); c.add_argument('output',type=Path)
    c.add_argument('--rules',type=Path,required=True)
    c.add_argument('--source-parent',type=Path,action='append',required=True); c.add_argument('--target-parent',type=Path,action='append',required=True)
    c.add_argument('--encoding',choices=['TAGGED','COMPACT'],default='COMPACT'); c.add_argument('--policy',choices=['ALL','SHORTER'],default='SHORTER')
    c.add_argument('--max-legend-bytes',type=int,default=1024*1024*1024); _publication_options(c); _composite_resource_options(c)
    c=group.add_parser('inspect'); c.add_argument('source',type=Path)
    for name in ('build','expand'):
        c=group.add_parser(name); c.add_argument('source',type=Path); c.add_argument('output',type=Path)
        if name=='build':
            c.add_argument('--rules',type=Path,required=True)
            c.add_argument('--encoding',choices=['TAGGED','COMPACT'],default='TAGGED')
            c.add_argument('--policy',choices=['ALL','SHORTER'],default='ALL')
        _publication_options(c); _composite_resource_options(c)
    for name in ('plan','encode','batch-encode'):
        c=sub.add_parser(name)
        if name=='batch-encode':
            c.add_argument('output',type=Path); c.add_argument('--source',dest='sources',action='append',required=True,type=Path)
            _composite_resource_options(c)
            c.add_argument('--max-source-bytes',type=int,default=1024*1024*1024)
            c.add_argument('--max-legend-bytes',type=int,default=1024*1024*1024)
            c.add_argument('--lookup-backend',choices=['AUTO','DISK','MMAP','RAM'],default='AUTO')
            c.add_argument('--backend-payload-budget-bytes',type=int,default=512*1024*1024)
            c.add_argument('--lookup-cache-root',type=Path)
        else: c.add_argument('source',type=Path)
        if name=='encode':
            c.add_argument('output',type=Path); _publication_options(c)
            c.add_argument('--max-scratch-bytes',type=int,default=4*1024**3,help='Primary realization logical scratch/native capacity, then output + receipt + backups + recovery journal; not RAM')
        c.add_argument('--profile',required=True)
        c.add_argument('--legend',action='append',default=[],type=Path)
        c.add_argument('--outer-codec',choices=REQUESTABLE_OUTER_CODECS,default='NONE',help='LZMA preserves the legacy LZMA2/XZ preset-6 realization; extended codecs use the v0.9 IC')
        c.add_argument('--legend-policy',choices=['TOTAL','PROFITABLE'],default=None)
        c.add_argument('--projection',choices=['PACKED','INTEGER','GLYPH'],default='PACKED',
            help='PACKED is the byte-efficient event stream; INTEGER is canonical inspectable decimal/hex text; GLYPH needs --glyph')
        c.add_argument('--glyph',type=Path)
        c.add_argument('--glyph-placement',choices=['EMBEDDED','EXTERNAL'],default='EMBEDDED')
        c.add_argument('--fold-front',type=Path,help='Explicit virtual .leg projection over exactly one pre-shared base; PACKED only')
        c.add_argument('--fold-placement',choices=['EMBEDDED','EXTERNAL'],default='EMBEDDED')
        c.add_argument('--accounting',choices=['COLD','WARM'],help='Folded profile dependency accounting; required for EXTERNAL')
        c.add_argument('--receiver-root',action='append',default=[],help='Exact external dependency root declared present at receiver')
    c=sub.add_parser('select'); c.add_argument('source',type=Path); c.add_argument('output',type=Path); _publication_options(c); _composite_resource_options(c)
    c.add_argument('--library',required=True,type=Path); c.add_argument('--legend',action='append',default=[],type=Path)
    c.add_argument('--accounting',choices=['WARM','COLD'],required=True)
    c.add_argument('--receiver-root',action='append',default=[])
    c.add_argument('--outer-codec',choices=['NONE','LZMA'],default='NONE')
    c.add_argument('--max-source-bytes',type=int,default=64*1024*1024); c.add_argument('--max-legend-bytes',type=int,default=1024*1024*1024)
    c=sub.add_parser('encode-selected'); c.add_argument('source',type=Path); c.add_argument('selection',type=Path); c.add_argument('output',type=Path); _publication_options(c); _composite_resource_options(c)
    c.add_argument('--library',required=True,type=Path); c.add_argument('--legend',action='append',default=[],type=Path)
    group=sub.add_parser('codec').add_subparsers(dest='action',required=True)
    c=group.add_parser('select'); c.add_argument('source',type=Path); c.add_argument('output',type=Path)
    c.add_argument('--profile',required=True); c.add_argument('--legend',action='append',default=[],type=Path)
    c.add_argument('--legend-policy',choices=['TOTAL','PROFITABLE'],default=None)
    c.add_argument('--codec',dest='codecs',action='append',choices=REQUESTABLE_OUTER_CODECS,
        help='Repeat to set ordered candidates; default is NONE/LZMA/XZ presets/BZ2 levels')
    c.add_argument('--accounting',choices=['COLD','WARM'],required=True)
    c.add_argument('--receiver-root',action='append',default=[])
    c.add_argument('--max-source-bytes',type=int,default=64*1024*1024)
    c.add_argument('--max-legend-bytes',type=int,default=1024*1024*1024)
    _publication_options(c); _composite_resource_options(c)
    c=group.add_parser('encode-selected'); c.add_argument('source',type=Path); c.add_argument('selection',type=Path); c.add_argument('output',type=Path)
    c.add_argument('--legend',action='append',default=[],type=Path)
    _publication_options(c); _composite_resource_options(c)
    group=sub.add_parser('library').add_subparsers(dest='action',required=True)
    c=group.add_parser('build'); c.add_argument('output',type=Path)
    c.add_argument('--member',nargs=3,action='append',required=True,metavar=('ID','FAMILY','LEGEND')); _publication_options(c); _artifact_resource_options(c)
    c=group.add_parser('build-stacks'); c.add_argument('output',type=Path)
    c.add_argument('--stack-member',nargs=4,action='append',required=True,metavar=('STACK_ID','FAMILY','ORDINAL','LEGEND')); _publication_options(c); _artifact_resource_options(c)
    group=sub.add_parser('configuration').add_subparsers(dest='action',required=True)
    c=group.add_parser('select'); c.add_argument('source',type=Path); c.add_argument('output',type=Path)
    c.add_argument('--library',required=True,type=Path); c.add_argument('--legend',action='append',required=True,default=[],type=Path)
    c.add_argument('--codec',dest='codecs',action='append',choices=REQUESTABLE_OUTER_CODECS,
        help='Repeat to set candidates; default is frozen NONE and LZMA')
    c.add_argument('--accounting',choices=['COLD','WARM'],required=True); c.add_argument('--receiver-root',action='append',default=[])
    c.add_argument('--horizon',type=int,default=1,help='1..1024 repetitions of this exact source workload; not future prediction')
    c.add_argument('--max-source-bytes',type=int,default=64*1024*1024); c.add_argument('--max-legend-bytes',type=int,default=1024*1024*1024)
    c.add_argument('--instrumentation',choices=['SENTINEL','DIAGNOSTIC'],default='SENTINEL')
    c.add_argument('--inverse-verification',choices=['ENCODER_POSTWRITE','INDEPENDENT_REDECODE'],default='ENCODER_POSTWRITE')
    c.add_argument('--lookup-backend',choices=['AUTO','DISK','MMAP','RAM'],default='AUTO')
    c.add_argument('--backend-payload-budget-bytes',type=int,default=512*1024*1024)
    c.add_argument('--lookup-cache-root',type=Path)
    _publication_options(c); _composite_resource_options(c)
    c=group.add_parser('encode-selected'); c.add_argument('source',type=Path); c.add_argument('selection',type=Path); c.add_argument('output',type=Path)
    c.add_argument('--library',required=True,type=Path); c.add_argument('--legend',action='append',required=True,default=[],type=Path)
    c.add_argument('--lookup-cache-root',type=Path)
    _publication_options(c); _composite_resource_options(c)
    c=sub.add_parser('decode'); c.add_argument('source',type=Path); c.add_argument('output',type=Path)
    c.add_argument('--legend',action='append',default=[],type=Path)
    c.add_argument('--glyph',type=Path)
    c.add_argument('--fold-front',type=Path,help='Resolve the exact external folded projection .leg')
    c.add_argument('--max-decoded-bytes',type=int,default=1<<40); c.add_argument('--max-container-bytes',type=int,default=1<<40)
    c.add_argument('--max-scratch-bytes',type=int,default=4*1024**3,help='Primary realization logical scratch/native capacity, then output + receipt + backups + recovery journal; not RAM')
    _publication_options(c)
    c=sub.add_parser('inspect'); c.add_argument('source',type=Path)
    archive=sub.add_parser('archive').add_subparsers(dest='action',required=True)
    for name in ('select','encode-selected'):
        c=archive.add_parser(name)
        if name=='encode-selected': c.add_argument('selection',type=Path); _composite_resource_options(c)
        c.add_argument('output',type=Path)
        c.add_argument('--source',dest='sources',action='append',required=True,type=Path)
        c.add_argument('--legend',required=True,type=Path)
        c.add_argument('--fold-front',dest='fronts',action='append',required=True,type=Path)
        if name=='select':
            _publication_options(c); _composite_resource_options(c)
            c.add_argument('--accounting',choices=['COLD','WARM'],required=True)
            c.add_argument('--receiver-root',action='append',default=[])
            c.add_argument('--outer-codec',choices=['NONE','LZMA'],default='NONE')
            c.add_argument('--horizon',type=int,default=1,help='1..32 repetitions of this identical workload, not future data prediction')
            c.add_argument('--max-source-bytes',type=int,default=64*1024*1024)
            c.add_argument('--max-legend-bytes',type=int,default=1024*1024*1024)
    group=sub.add_parser('fold').add_subparsers(dest='action',required=True)
    c=group.add_parser('compact'); c.add_argument('source',type=Path,help='rich projection .leg file'); c.add_argument('output',type=Path,help='new bundle directory (not a .leg file)'); _composite_resource_options(c)
    c=group.add_parser('audit'); c.add_argument('source',type=Path,help='compact .leg file inside the bundle, not the bundle directory'); c.add_argument('--provenance',type=Path,required=True)
    c=group.add_parser('restore-rich'); c.add_argument('source',type=Path); c.add_argument('output',type=Path)
    c.add_argument('--provenance',type=Path,required=True); _publication_options(c); _composite_resource_options(c)
    c=group.add_parser('delivery-cost'); c.add_argument('source',type=Path)
    c.add_argument('--policy',required=True,choices=['EXECUTION_ONLY','EXECUTION_AND_AUDIT'])
    c.add_argument('--provenance',type=Path); c.add_argument('--receiver-root',action='append',default=[])
    c.add_argument('--container-bytes',type=int,default=0); c.add_argument('--horizon',type=int,default=1)
    c=group.add_parser('prefix'); c.add_argument('source',type=Path); c.add_argument('output',type=Path)
    c.add_argument('--front-cap',type=int,required=True); _publication_options(c); _composite_resource_options(c)
    c=group.add_parser('build'); c.add_argument('source',type=Path); c.add_argument('output',type=Path); _publication_options(c); _composite_resource_options(c)
    c.add_argument('--legend',action='append',required=True,type=Path)
    c.add_argument('--calibration',action='append',default=[],type=Path,help='Additional ordered calibration documents; never evaluation inputs')
    c.add_argument('--front-cap',type=int,default=4096)
    c.add_argument('--max-calibration-bytes',type=int,default=64*1024*1024)
    c=group.add_parser('extract'); c.add_argument('source',type=Path); c.add_argument('output',type=Path); _publication_options(c); _composite_resource_options(c)
    group=sub.add_parser('legend').add_subparsers(dest='action',required=True)
    c=group.add_parser('build'); c.add_argument('source',type=Path); c.add_argument('output',type=Path)
    c.add_argument('--policy',choices=['TOTAL','PROFITABLE'],default='TOTAL'); _publication_options(c); _artifact_resource_options(c)
    c=group.add_parser('migrate-v01'); c.add_argument('source',type=Path); c.add_argument('output',type=Path); _publication_options(c); _artifact_resource_options(c)
    c=group.add_parser('import-ordered-v01'); c.add_argument('source',type=Path); c.add_argument('output',type=Path); _publication_options(c); _artifact_resource_options(c)
    c.add_argument('--expected-source-sha256',required=True)
    c.add_argument('--max-source-bytes',type=int,default=1024*1024*1024); c.add_argument('--max-entries',type=int,default=10000000)
    c.add_argument('--max-value-bytes',type=int,default=16*1024*1024)
    c=group.add_parser('extract'); c.add_argument('source',type=Path); c.add_argument('output',type=Path)
    c.add_argument('--binding-index',type=int,required=True,help='zero-based index in the .crys header legend stack'); _publication_options(c); _artifact_resource_options(c)
    group=sub.add_parser('glyph').add_subparsers(dest='action',required=True)
    c=group.add_parser('build'); c.add_argument('output',type=Path); c.add_argument('--glyphs',required=True); c.add_argument('--name',required=True); _publication_options(c); _artifact_resource_options(c)
    c=group.add_parser('export'); c.add_argument('source',type=Path); c.add_argument('output',type=Path)
    c.add_argument('--legend',action='append',default=[],type=Path); c.add_argument('--glyph',type=Path)
    c.add_argument('--max-decoded-bytes',type=int,default=1<<40); c.add_argument('--max-container-bytes',type=int,default=1<<40); _publication_options(c); _artifact_resource_options(c)
    return p

def main(argv=None):
    raw=list(sys.argv[1:] if argv is None else argv)
    if raw==['--help-json']:raw=['help-json']
    path_index=2 if len(raw)>=2 and raw[0]=='--progress' else 0
    command_parser=parser()
    commands=next(a for a in command_parser._actions if isinstance(a,argparse._SubParsersAction)).choices
    if len(raw)>path_index and raw[path_index] not in commands and not raw[path_index].startswith('-') and Path(raw[path_index]).exists():
        raw.insert(path_index,'pack')
    args=command_parser.parse_args(raw)
    try:
        integrity=verify_self()
        if args.command=='verify-self': result=integrity
        elif args.command=='help-json': result=surface()
        elif args.command=='explain-default': result=standard_archive.default_contract()
        elif args.command=='pack':
            def progress(event): emit_progress(event,args.progress)
            registry=json.loads(args.registry.read_text(encoding='utf-8')) if args.registry else None
            cache=None if args.no_cache else (args.cache_root or _standard_cache_root())
            result=standard_archive.pack(args.inputs,args.output,mode=args.mode,registry=registry,
                cache_root=cache,workers=args.workers,chunk_bytes=args.chunk_bytes,
                composition=args.composition,dry_run=args.dry_run,progress=progress)
        elif args.command=='unpack':
            def progress(event): emit_progress(event,args.progress)
            result=standard_archive.unpack(args.source,args.output,only=args.only,
                max_output_bytes=args.max_output_bytes,progress=progress)
        elif args.command=='list': result=standard_archive.list_entries(args.source)
        elif args.command=='verify':
            def progress(event): emit_progress(event,args.progress)
            result=standard_archive.verify(args.source,max_output_bytes=args.max_output_bytes,progress=progress)
        elif args.command=='search': result=standard_archive.search(args.source,args.query)
        elif args.command=='synchronize':
            if args.action=='disclosure': result=sync_disclosure(args.source,args.legend,max_entries=args.max_entries)
            elif args.action=='ordering': result=sync_ordering(args.source,args.legend,max_entries=args.max_entries)
            elif args.action=='compose': result=sync_compose(args.source,args.legend,minimum_count=args.minimum_count,max_entries=args.max_entries)
            else: result=sync_account(args.source,args.container,args.legend)
        elif args.command=='archaic':
            result=archaic_registry() if args.action=='profiles' else compile_archaic_plan(args.source,role=args.role,
                external_legends=args.legend,outer_codec=args.outer_codec,legend_policy=args.legend_policy,
                projection=args.projection,glyph_registry=args.glyph,glyph_placement=args.glyph_placement,
                meaning_mode=args.meaning_mode,shuffle_mode=args.shuffle_mode)
        elif args.command=='transport':
            if args.action=='capabilities': result=transport_capabilities()
            elif args.action=='negotiate': result=negotiate_transport(load_peer(args.local),load_peer(args.remote),
                requested_pathway=args.pathway,requested_codec=args.codec,requested_projection=args.projection,
                requested_legend_roots=args.legend_root,self_contained=args.self_contained,requested_security_mode=args.security_mode)
            elif args.action=='frame': result=compile_frame(args.body,load_frame(args.negotiation))
            else: result=verify_frame(load_frame(args.frame),args.body,load_frame(args.negotiation))
        elif args.command=='gtk':
            if args.action=='capabilities': result=gtk_capabilities()
            elif args.action=='analyze':
                result=analyze_gtk(args.source,schema_contract=args.schema_contract,dossiers=args.dossier,
                    decisions=args.decisions,legends=args.legend,pathway=args.pathway,sense_binding=args.sense_binding,
                    unresolved=args.sense_unresolved,force_csil=args.force_csil,annotate=args.annotate=='ON',
                    max_source_bytes=args.max_source_bytes,max_units=args.max_units,max_annotations=args.max_annotations,
                    max_legend_bytes=args.max_legend_bytes)
            elif args.action=='verify-vocabulary': result=verify_vocabulary(args.source,legends=args.legend,max_legend_bytes=args.max_legend_bytes)
            else:
                def progress(event): emit_progress(event,args.progress)
                result=publish(lambda stage:export_vocabulary(stage,legends=args.legend,
                    acknowledge_legend_disclosure=args.acknowledge_legend_disclosure,max_legend_bytes=args.max_legend_bytes),args.output,
                    inputs=args.legend,receipt=args.receipt,replace=args.replace,max_scratch_bytes=args.max_scratch_bytes,
                    resource_operation='GTK_VOCABULARY_EXPORT',progress=progress,
                    metadata={'application_version':__version__,'application_payload_root':integrity['payload_root']})
        elif args.command=='security':
            if args.action=='inspect':result=protected_artifact.inspect_bytes(args.source.read_bytes())
            elif args.action=='protect':
                result=protected_artifact.protect_file(args.source,args.output,key=_secure_key(args),role=args.role,
                    padding_policy=args.padding,padding_bucket=args.padding_bucket)
            elif args.action=='unprotect':
                result=protected_artifact.unprotect_file(args.source,args.output,key=_secure_key(args))
            elif args.action=='verify':
                _plaintext,result=protected_artifact.unprotect_bytes(args.source.read_bytes(),key=_secure_key(args))
            else:
                envelope,result=protected_artifact.rotate_bytes(args.source.read_bytes(),old_key=_secure_key(args,old=True),new_key=_secure_key(args))
                protected_artifact.write_atomic(args.output,envelope)
        elif args.command=='workbench':
            result=workbench_status(include_rows=args.rows) if args.action=='status' else workbench_export()
        elif args.command=='profiles': result=catalogue()
        elif args.command=='capabilities': result=surface()
        elif args.command=='formats': result=format_registry()
        elif args.command=='inspect':
            viewed=inspect_artifact(args.source)
            result=standard_archive.inspect(args.source) if viewed.get('configuration',{}).get('schema')==standard_archive.SCHEMA else viewed
        elif args.command=='recovery':
            if args.action=='inspect':result=recovery_inspect(args.journal,args.expected_journal_root)
            elif args.action=='directory-inspect':result=directory_recovery.inspect(args.journal,args.expected_journal_root)
            elif args.action=='directory-quarantine':
                def progress(event):emit_progress(event,args.progress)
                result=directory_recovery.quarantine(args.journal,output=args.output,expected_root=args.expected_journal_root,progress=progress)
            else:
                def progress(event):emit_progress(event,args.progress)
                result=recovery_rollback(args.journal,output=args.output,receipt=args.receipt,
                    expected_root=args.expected_journal_root,progress=progress)
        elif args.command in ('group-legend','metalegend'):
            def progress(event): emit_progress(event,args.progress)
            if args.action=='pack':
                result=pack_meta(args.output,sources=args.source,legends=args.legend,glyphs=args.glyphs,fold_fronts=args.fold_fronts,placement=args.placement,
                    selection=args.selection,outer_codec=args.outer_codec,max_input_bytes=args.max_input_bytes,progress=progress,
                    layout=args.layout,accounting=args.accounting,receiver_roots=args.receiver_root,shared_pool=args.shared_pool,max_scratch_bytes=args.max_scratch_bytes)
            elif args.action=='unpack': result=unpack_meta(args.source,args.output,meta=args.meta,max_output_bytes=args.max_output_bytes,progress=progress,max_scratch_bytes=args.max_scratch_bytes)
            elif args.action=='build': result=build_recursive_meta(args.source,args.output,layout=args.layout,
                block_entries=args.block_entries,frame_blocks=args.frame_blocks,require_smaller=not args.allow_expansion)
            elif args.action=='restore': result=restore_recursive_meta(args.source,args.output)
            elif args.action=='inspect': result=inspect_recursive_meta(args.source,verify_frames=not args.fast)
            elif args.action=='verify': result=verify_recursive_meta(args.source)
            elif args.action=='lookup':
                reader=SeekableMetalegendReader(args.source,cache_root=args.cache_root,cache_profile=args.cache_profile)
                values=reader.get_many(args.identifier)
                result={'schema':'semcrys.metalegend-lookup-result.v0.1','status':'PASS',
                    'source':str(args.source),'values':[{'identifier':identifier,'bytes':len(values[identifier]),
                    'sha256':__import__('hashlib').sha256(values[identifier]).hexdigest(),'hex':values[identifier].hex()}
                    for identifier in args.identifier],'reader':reader.receipt()}
            else:
                reader=SeekableMetalegendReader(args.source,cache_root=args.cache_root,cache_profile=args.cache_profile)
                path=reader.prepare_full_cache()
                result={'schema':'semcrys.metalegend-prepare-result.v0.1','status':'PASS','path':str(path),
                    'sha256':file_sha256(path),'bytes':path.stat().st_size,'reader':reader.receipt()}
        elif args.command=='second-pass':
            def progress(event): emit_progress(event,args.progress)
            result=publish(lambda stage:second_pass(args.source,stage,external_legends=args.legend,selection=args.selection,
                accounting=args.accounting,rounds=args.rounds,min_count=args.min_count,hot_k=args.hot_k,max_source_bytes=args.max_source_bytes,
                max_events=args.max_events,progress=progress,max_scratch_bytes=args.max_scratch_bytes),args.output,inputs=[args.source,*args.legend],
                receipt=args.receipt,replace=args.replace,max_scratch_bytes=args.max_scratch_bytes,progress=progress,
                metadata={'application_version':__version__,'application_payload_root':integrity['payload_root']})
        elif args.command=='assembly':
            if args.action=='inspect': result=inspect_assembly(args.source)
            else:
                def progress(event): emit_progress(event,args.progress)
                resource_operation='ASSEMBLY_'+args.action.replace('-','_').upper()
                options={}; inputs=[args.source]
                if args.action!='expand':options.update(rules=args.rules,encoding=args.encoding);inputs.append(args.rules)
                if args.action in ('build','build-delta'):options['policy']=args.policy
                if args.action=='build-delta':
                    options.update(source_parents=args.source_parent,target_parents=args.target_parent,max_legend_bytes=args.max_legend_bytes)
                    inputs.extend([*args.source_parent,*args.target_parent])
                if args.action in ('encode','encode-longitudinal'):
                    options.update(outer_codec=args.outer_codec,record_policy=args.policy,selection=args.selection,max_source_bytes=args.max_source_bytes)
                    if args.action=='encode':options['legend_policy']=args.legend_policy
                    else:
                        options.update(external_legends=args.legend,max_legend_bytes=args.max_legend_bytes);inputs.extend(args.legend)
                result=publish(lambda stage:application.run(resource_operation,args.source,stage,
                    max_scratch_bytes=args.max_scratch_bytes,progress=progress,**options),
                    args.output,inputs=inputs,receipt=args.receipt,replace=args.replace,
                    max_scratch_bytes=args.max_scratch_bytes,resource_operation=resource_operation,progress=progress,
                    metadata={'application_version':__version__,'application_payload_root':integrity['payload_root']})
        elif args.command=='fold' and args.action=='compact':
            def progress(event):emit_progress(event,args.progress)
            result=directory_application.run('FOLD_COMPACT',args.source,args.output,max_scratch_bytes=args.max_scratch_bytes,progress=progress)
        elif args.command=='fold' and args.action=='audit': result=audit_front(args.source,args.provenance)
        elif args.command=='fold' and args.action=='delivery-cost':
            result=delivery_cost(args.source,policy=args.policy,provenance=args.provenance,
                receiver_roots=args.receiver_root,container_bytes=args.container_bytes,horizon=args.horizon)
        elif args.command=='archive':
            def progress(event): emit_progress(event,args.progress)
            if args.action=='select':
                result=publish(lambda stage:application.run('ARCHIVE_SELECT',None,stage,sources=args.sources,base=args.legend,fronts=args.fronts,
                    accounting=args.accounting,receiver_roots=args.receiver_root,outer_codec=args.outer_codec,horizon=args.horizon,
                    max_source_bytes=args.max_source_bytes,max_legend_bytes=args.max_legend_bytes,progress=progress,max_scratch_bytes=args.max_scratch_bytes),
                    args.output,inputs=[*args.sources,args.legend,*args.fronts],receipt=args.receipt,replace=args.replace,
                    max_scratch_bytes=args.max_scratch_bytes,resource_operation='ARCHIVE_SELECT',progress=progress,
                    metadata={'application_version':__version__,'application_payload_root':integrity['payload_root']})
            else:
                result=directory_application.run('ARCHIVE_ENCODE_SELECTED',args.selection,args.output,sources=args.sources,base=args.legend,
                    fronts=args.fronts,progress=progress,max_scratch_bytes=args.max_scratch_bytes)
        elif args.command=='batch-encode':
            def progress(event): emit_progress(event,args.progress)
            result=directory_application.run('BATCH_ENCODE',None,args.output,sources=args.sources,profile=args.profile,external_legends=args.legend,
                outer_codec=args.outer_codec,legend_policy=args.legend_policy,projection=args.projection,glyph_registry=args.glyph,glyph_placement=args.glyph_placement,
                fold_front=args.fold_front,fold_placement=args.fold_placement,accounting=args.accounting,receiver_roots=args.receiver_root,
                max_source_bytes=args.max_source_bytes,max_legend_bytes=args.max_legend_bytes,lookup_backend=args.lookup_backend,
                backend_payload_budget_bytes=args.backend_payload_budget_bytes,persistent_lookup_cache=args.lookup_cache_root,
                progress=progress,max_scratch_bytes=args.max_scratch_bytes)
        elif args.command=='plan':
            result=compile_funnel(source_sha256=file_sha256(args.source),profile=args.profile,external_legends=args.legend,
                outer_codec=args.outer_codec,legend_policy=args.legend_policy,projection=args.projection,glyph_registry=args.glyph,glyph_placement=args.glyph_placement,fold_front=args.fold_front,
                fold_placement=args.fold_placement,accounting=args.accounting,receiver_roots=args.receiver_root)
        elif args.command=='codec':
            def progress(event): emit_progress(event,args.progress)
            resource_operation='CODEC_SELECT' if args.action=='select' else 'CODEC_ENCODE_SELECTED'
            inputs=[args.source,*args.legend]
            if args.action=='encode-selected': inputs.append(args.selection)
            def operation(stage):
                if args.action=='select':
                    return application.run(resource_operation,args.source,stage,profile=args.profile,
                        external_legends=args.legend,legend_policy=args.legend_policy,
                        codecs=args.codecs or DEFAULT_CODECS,accounting=args.accounting,
                        receiver_roots=args.receiver_root,max_source_bytes=args.max_source_bytes,
                        max_legend_bytes=args.max_legend_bytes,max_scratch_bytes=args.max_scratch_bytes,progress=progress)
                return application.run(resource_operation,args.source,stage,selection_path=args.selection,
                    external_legends=args.legend,max_scratch_bytes=args.max_scratch_bytes,progress=progress)
            result=publish(operation,args.output,inputs=inputs,receipt=args.receipt,replace=args.replace,
                max_scratch_bytes=args.max_scratch_bytes,resource_operation=resource_operation,progress=progress,
                metadata={'application_version':__version__,'application_payload_root':integrity['payload_root']})
        elif args.command=='configuration':
            def progress(event): emit_progress(event,args.progress)
            resource_operation='CONFIGURATION_SELECT' if args.action=='select' else 'CONFIGURATION_ENCODE_SELECTED'
            inputs=[args.source,args.library,*args.legend]
            if args.action=='encode-selected': inputs.append(args.selection)
            def operation(stage):
                if args.action=='select':
                    return application.run(resource_operation,args.source,stage,library_path=args.library,
                        legends=args.legend,codecs=args.codecs or ('NONE','LZMA'),accounting=args.accounting,
                        receiver_roots=args.receiver_root,horizon=args.horizon,max_source_bytes=args.max_source_bytes,
                        max_legend_bytes=args.max_legend_bytes,instrumentation=args.instrumentation,
                        inverse_verification=args.inverse_verification,lookup_backend=args.lookup_backend,
                        backend_payload_budget_bytes=args.backend_payload_budget_bytes,
                        persistent_lookup_cache=args.lookup_cache_root,max_scratch_bytes=args.max_scratch_bytes,progress=progress)
                return application.run(resource_operation,args.source,stage,selection_path=args.selection,
                    library_path=args.library,legends=args.legend,persistent_lookup_cache=args.lookup_cache_root,
                    max_scratch_bytes=args.max_scratch_bytes,progress=progress)
            result=publish(operation,args.output,inputs=inputs,receipt=args.receipt,replace=args.replace,
                max_scratch_bytes=args.max_scratch_bytes,resource_operation=resource_operation,progress=progress,
                metadata={'application_version':__version__,'application_payload_root':integrity['payload_root']})
        else:
            inputs=([args.source] if hasattr(args,'source') else [])+getattr(args,'legend',[])
            if getattr(args,'glyph',None) is not None: inputs.append(args.glyph)
            if getattr(args,'library',None) is not None: inputs.append(args.library)
            if getattr(args,'selection',None) is not None: inputs.append(args.selection)
            if getattr(args,'fold_front',None) is not None: inputs.append(args.fold_front)
            if getattr(args,'provenance',None) is not None: inputs.append(args.provenance)
            for key in ('legacy_legend','legacy_glyph'):
                if getattr(args,key,None) is not None:inputs.append(getattr(args,key))
            inputs.extend(getattr(args,'calibration',[]))
            if args.command=='library':
                if args.action=='build':inputs.extend(Path(row[2]) for row in args.member)
                else:inputs.extend(Path(row[3]) for row in args.stack_member)
            def resource_progress(event):emit_progress(event,args.progress)
            resource_operation=(args.command.upper() if args.command in ('encode','decode') else
                {'legend build':'LEGEND_BUILD','legend migrate-v01':'LEGEND_MIGRATE_V01',
                 'legend import-ordered-v01':'LEGEND_IMPORT_ORDERED_V01','legend extract':'LEGEND_EXTRACT',
                 'glyph build':'GLYPH_BUILD','glyph export':'GLYPH_EXPORT','library build':'LIBRARY_BUILD','library build-stacks':'STACK_LIBRARY_BUILD',
                 'fold build':'FOLD_BUILD','fold prefix':'FOLD_PREFIX','fold extract':'FOLD_EXTRACT','fold restore-rich':'FOLD_RESTORE_RICH',
                 'select ':'SELECT','encode-selected ':'ENCODE_SELECTED','legacy import':'LEGACY_IMPORT'}
                .get(args.command+' '+getattr(args,'action','')))
            def artifact_run(stage,**options):
                return application.run(resource_operation,getattr(args,'source',None),stage,
                    max_scratch_bytes=args.max_scratch_bytes,progress=resource_progress,**options)
            def operation(stage):
                if args.command=='legacy':
                    return artifact_run(stage,format=args.format,expected_source_sha256=args.expected_source_sha256,
                        legacy_legend=args.legacy_legend,legacy_glyph=args.legacy_glyph,profile=args.profile,
                        external_legends=args.legend,outer_codec=args.outer_codec,legend_policy=args.legend_policy,
                        max_source_bytes=args.max_source_bytes,max_decoded_bytes=args.max_decoded_bytes)
                if args.command=='fold':
                    if args.action=='restore-rich': return artifact_run(stage,provenance=args.provenance)
                    if args.action=='extract': return artifact_run(stage)
                    if args.action=='prefix': return artifact_run(stage,front_cap=args.front_cap)
                    return artifact_run(stage,external_legends=args.legend,additional_sources=args.calibration,
                        front_cap=args.front_cap,max_calibration_bytes=args.max_calibration_bytes)
                if args.command=='library':
                    if args.action=='build':return artifact_run(stage,members=args.member)
                    return artifact_run(stage,stack_members=args.stack_member)
                if args.command=='select':
                    return artifact_run(stage,library_path=args.library,legends=args.legend,accounting=args.accounting,
                        receiver_roots=args.receiver_root,outer_codec=args.outer_codec,max_source_bytes=args.max_source_bytes,max_legend_bytes=args.max_legend_bytes)
                if args.command=='encode-selected':
                    return artifact_run(stage,selection_path=args.selection,library_path=args.library,legends=args.legend)
                if args.command=='encode':
                    return application.encode(args.source,stage,profile=args.profile,external_legends=args.legend,
                        outer_codec=args.outer_codec,legend_policy=args.legend_policy,projection=args.projection,glyph_registry=args.glyph,glyph_placement=args.glyph_placement,fold_front=args.fold_front,
                        fold_placement=args.fold_placement,accounting=args.accounting,receiver_roots=args.receiver_root,
                        max_scratch_bytes=args.max_scratch_bytes,progress=resource_progress)
                if args.command=='decode':
                    return application.decode(args.source,stage,external_legends=args.legend,glyph_registry=args.glyph,fold_front=args.fold_front,max_decoded_bytes=args.max_decoded_bytes,max_container_bytes=args.max_container_bytes,
                        max_scratch_bytes=args.max_scratch_bytes,progress=resource_progress)
                if args.command=='legend':
                    if args.action=='build': return artifact_run(stage,policy=args.policy)
                    if args.action=='migrate-v01': return artifact_run(stage)
                    if args.action=='import-ordered-v01':
                        def progress(event): emit_progress(event,args.progress)
                        return artifact_run(stage,expected_source_sha256=args.expected_source_sha256,max_source_bytes=args.max_source_bytes,max_entries=args.max_entries,max_value_bytes=args.max_value_bytes)
                    return artifact_run(stage,binding_index=args.binding_index)
                if args.command=='glyph':
                    if args.action=='export': return artifact_run(stage,external_legends=args.legend,glyph_registry=args.glyph,max_decoded_bytes=args.max_decoded_bytes,max_container_bytes=args.max_container_bytes)
                    return artifact_run(stage,glyphs=args.glyphs,name=args.name)
                raise Refusal('HELD_COMMAND_UNAVAILABLE')
            result=publish(operation,args.output,inputs=inputs,receipt=args.receipt,replace=args.replace,
                **({'max_scratch_bytes':args.max_scratch_bytes,'resource_operation':resource_operation,'progress':resource_progress} if resource_operation else {}),
                metadata={'application_version':__version__,'application_payload_root':integrity['payload_root']})
        result={**result,'application_version':__version__,'application_payload_root':integrity['payload_root']}
        print(json.dumps(result,ensure_ascii=True,sort_keys=True)); return 0
    except KeyboardInterrupt:
        atomic=getattr(args,'command',None)=='pack'
        print(json.dumps({'status':'HELD','code':'HELD_INTERRUPTED',
            'completion':'DESTINATION_ABSENT_OR_COMPLETE' if atomic else 'UNKNOWN_INSPECT_DESTINATION',
            'detail':('Interrupted before atomic publication; verified cache checkpoints remain reusable. '
                      'If the destination exists, it was fully verified before rename.' if atomic else
                      'Interrupted. Inspect destination and receipts before retrying; publication may already have completed.')},
            ensure_ascii=True)); return 130
    except (ValueError,OSError,sqlite3.Error) as exc:
        code=getattr(exc,'code','HELD_IO_OR_VALUE_ERROR'); detail=str(exc)
        if code=='HELD_LEG_SUFFIX_REQUIRED' and args.command=='fold':
            hint={
                'compact':'fold compact expects a rich SOURCE.leg and a NEW_BUNDLE_DIRECTORY output.',
                'audit':'fold audit expects the compact .leg FILE inside the bundle, plus --provenance DOSSIER.json.',
                'restore-rich':'fold restore-rich expects a compact SOURCE.leg, an OUTPUT.leg and --provenance DOSSIER.json.',
                'delivery-cost':'fold delivery-cost expects the execution projection .leg FILE, not its bundle directory.',
            }.get(args.action)
            if hint: detail+='; '+hint
        print(json.dumps({'status':'HELD','code':code,'detail':detail},ensure_ascii=True)); return 1

if __name__=='__main__': raise SystemExit(main())
