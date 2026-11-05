"""Rooted current ABI/profile contract, not a claim of full qualification.
SPDX-License-Identifier: Apache-2.0
"""
import hashlib
from streaming_legend import abi,core,crys_v2,fold,glyph,assembly
from streaming_app import core as application,integer_projection
from . import (second_pass, group_legend, group_bundle, group_auxiliary,
               recursive_metalegend, seekable_metalegend, transport, gtk_analysis)

COMMON_FIELDS=('schema','standing','predecessor_head','profile','source_sha256','external_legend_roots',
 'outer_codec','legend_policy','tokenizer','max_unit_bytes','oversize_policy','implicit_fallback','security_claim',
 'legend_stack','physical_body_schema','instance_constitution_sha256')
GLYPH_FIELDS=('projection','glyph_registry_sha256','glyph_placement','glyph_codec','glyph_radix',
 'glyph_literal_escape','glyph_width','glyph_legend_entries')
INTEGER_FIELDS=('projection','integer_codec','integer_legend_entries')
FORM_FIELDS=('assembly_legend_roots','assembly_abi')
FOLD_FIELDS=('fold_projection','fold_fallback')
COMPOSED_FIELDS=('schema','standing','predecessor_head','profile','source_sha256','external_legend_roots',
 'outer_codec','legend_stack','physical_body_schema','implicit_fallback','security_claim','second_pass','instance_constitution_sha256')
META_FIELDS=('schema','standing','profile','source_manifest','manifest_sha256','pool_sha256','pool_entries','placement',
 'mode','outer_codec','body_schema','limits','operation_sequence','security_claim','implicit_fallback','instance_constitution_sha256')
PROFILES=('C:RAW_BYTES','C:SELF_CONTAINED_TOKEN','T:PRESHARED_TOKEN','A:LONGITUDINAL_TOKEN_DELTA')
EXTENDED_FIELDS=COMMON_FIELDS+('outer_codec_configuration',)

def registry():
    def variant(n,feature,profiles,body,fields,decoder='decode'):
        return {'id':feature,'instance_schema':'semcrys.instance-constitution.v0.'+str(n),
          'profiles':list(profiles),'body_schemas':body,'exact_top_level_fields':sorted(fields),'decoder':decoder}
    rows=[variant(2,'ORDINARY',PROFILES,['semcrys.raw-body.v0.2','semcrys.packed-token.v0.2'],COMMON_FIELDS),
      variant(9,'ORDINARY_EXTENDED_OUTER_CODEC',PROFILES,['semcrys.raw-body.v0.2','semcrys.packed-token.v0.2'],EXTENDED_FIELDS),
      variant(3,'GLYPH',PROFILES[1:],['semcrys.glyph-token.v0.1'],COMMON_FIELDS+GLYPH_FIELDS),
      variant(10,'INTEGER',PROFILES[1:],['semcrys.integer-token.v0.1'],COMMON_FIELDS+INTEGER_FIELDS),
      variant(4,'FOLD_EMBEDDED',[PROFILES[2]],['semcrys.folded-front-packed.v0.1'],COMMON_FIELDS+FOLD_FIELDS),
      variant(5,'FOLD_EXTERNAL',[PROFILES[2]],['semcrys.folded-front-packed.v0.1'],COMMON_FIELDS+FOLD_FIELDS),
      variant(6,'FORM_TAGGED',PROFILES[1:],['semcrys.packed-token.v0.2'],COMMON_FIELDS+FORM_FIELDS),
      variant(7,'FORM_COMPACT',PROFILES[1:],['semcrys.packed-token.v0.2'],COMMON_FIELDS+FORM_FIELDS),
      variant(8,'COMPOSED',['C:COMPOSED_SECOND_PASS'],[second_pass.BODY_SCHEMA],COMPOSED_FIELDS),
      variant(11,'COMPOSED_TOPK',['C:COMPOSED_SECOND_PASS'],[second_pass.BODY_SCHEMA],COMPOSED_FIELDS),
      {'id':'GROUP_LEGEND_ARCHIVE','legacy_id':'META_ARCHIVE','instance_schema':group_legend.SCHEMA,'profiles':['B:METALEGEND_ARCHIVE'],
       'body_schemas':['semcrys.metalegend-body.v0.1'],'exact_top_level_fields':sorted(META_FIELDS),'decoder':'group-legend unpack'},
      {'id':'GROUP_LEGEND_BUNDLE','legacy_id':'META_BUNDLE','instance_schema':group_bundle.SCHEMA,'profiles':['B:METALEGEND_BUNDLE'],
       'body_schemas':[group_bundle.BODY_SCHEMA],'exact_top_level_fields':sorted(group_bundle.FIELDS),'decoder':'group-legend unpack'},
      {'id':'GROUP_LEGEND_ARCHIVE_AUX','legacy_id':'META_ARCHIVE_AUX','instance_schema':group_auxiliary.SCHEMA,'profiles':['B:METALEGEND_ARCHIVE'],
       'body_schemas':['semcrys.metalegend-body.v0.1'],'exact_top_level_fields':sorted(META_FIELDS+('auxiliary_contract_root',)),
       'decoder':'group-legend unpack'},
      {'id':'GROUP_LEGEND_BUNDLE_AUX','legacy_id':'META_BUNDLE_AUX','instance_schema':group_auxiliary.BUNDLE_SCHEMA,'profiles':['B:METALEGEND_BUNDLE'],
       'body_schemas':[group_bundle.BODY_SCHEMA],'exact_top_level_fields':sorted(group_bundle.FIELDS),'decoder':'group-legend unpack'}]
    result={'schema':'semcrys.abi-profile-registry.v0.1','standing':'CANDIDATE_ONLY',
      'stability':'CANDIDATE_NORMATIVE_SNAPSHOT_NOT_RELEASE_ACCEPTANCE',
      'funnel':{'S':'TOTAL_DECLARED_PHASE_SPACE','CM1':'FUNCTIONAL_FORMAT_DEPENDENCY_AND_RESOURCE_ADMISSIBILITY',
       'CM2':'OPTIMIZATION_WITH_COST_OBJECTIVE_AND_RECEIVER_STATE','IC':'SELECTED_ROOTED_CONFIGURATION',
       'IR':'ACTUAL_BYTES_AND_VERIFIED_RESULT'},
      'artifacts':{
       'container':{'suffix':'.crys','magic_hex':crys_v2.MAGIC.hex(),'version':list(crys_v2.VERSION),
        'prologue':crys_v2.PROLOGUE.format,'section':crys_v2.SECTION.format,
        'known_sections':sorted(x.decode('ascii') for x in crys_v2.KNOWN),
        'section_ranks':{k.decode('ascii'):v for k,v in crys_v2.RANK.items()},
        'critical_bit':crys_v2.CRITICAL,'unknown_critical':'REFUSE','unknown_noncritical':'HASH_VALIDATE_AND_SKIP',
        'header_schema':'semcrys.crys.header.v0.2','decoded_root':'SOURCE_BYTES_EXCEPT_META_ARCHIVE_INVENTORY_ROOT'},
       'legend':{'suffix':'.leg','magic_hex':core.MAGIC.hex(),'version':list(core.VERSION),
        'prologue':core.PROLOGUE.format,'footer':core.FOOTER.format,'index_entry':core.U64.format,
        'header_schema':'semcrys.legend.binary.v0.2','header_fields':
        ['schema','standing','legend_id','unit_mode','parent_sha256','entry_count','index_stride'],
        'id_base':1,'id_meaning':'ROOT_AND_ORDER_SCOPED_NOT_CANONICAL_CSIL',
        'recognized_unit_modes':list(abi.RECOGNIZED_UNIT_MODES),'unknown_mode_execution':'REFUSE',
        'opaque_storage':'RAW_STRUCTURAL_READER_MAY_INSPECT_WITHOUT_EXECUTING'},
       'fold':{'suffix':'.leg','magic_hex':fold.MAGIC.hex(),'schemas':[fold.SCHEMA,fold.COMPACT_SCHEMA],
        'prefix':'MAGIC8_U32BE_CANONICAL_JSON_HEADER_LENGTH_HEADER_SIGNAL','base_mode':'TOKEN',
        'signal_codec':fold.SIGNAL_CODEC,'rich_vs_compact':'AUDIT_PROVENANCE_SPLIT_NOT_IDENTITY_CHANGE'},
       'recursive_metalegend':{'suffix':'.mleg','dialects':[
        {'magic_hex':seekable_metalegend.MAGIC.hex(),'schema':seekable_metalegend.SCHEMA,
         'profile':seekable_metalegend.PROFILE,'targeted_lookup':True},
        {'magic_hex':recursive_metalegend.MAGIC.hex(),'schema':recursive_metalegend.SCHEMA,
         'profile':'RECURSIVE_PREFIX_RECIPE_V1','targeted_lookup':False}],
        'recursion_depth':1,
        'logical_input':'ORDERED_LEGEND_RECORDS_NOT_OPAQUE_LEGEND_BYTES',
        'inverse_root':'EXACT_ORIGINAL_LEGEND_BYTES','nested_input':'REFUSE'},
       'glyph':{'suffix':'.gly','schema':'semcrys.glyph-registry.v0.1','serialization':'CANONICAL_UTF8_JSON',
        'kinds':['TEMPLATE','BOUND'],'execution_kind':'TEMPLATE_ONLY','fields':['schema','standing','name','kind','glyphs','bindings']}
      },
      'body_grammars':{
       'RAW2':{'magic_hex':application.RAW_MAGIC.hex(),'grammar':'MAGIC4 || EXACT_SOURCE_BYTES'},
       'SPV2':{'magic_hex':application.PACKED_MAGIC.hex(),'grammar':'MAGIC4 || (ULEB128(id>0) | 0 || ULEB128(length) || literal_bytes)*'},
       'SGY1':{'magic_hex':b'SGY1\n'.hex(),'grammar':'MAGIC5 || FIXED_WIDTH_BASE_N_IDS_OR_EXPLICIT_ESCAPED_LITERALS'},
       'SIT1':{'magic_hex':integer_projection.MAGIC.hex(),
        'grammar':'MAGIC5 || (I:CANONICAL_DECIMAL_LEGEND_ID_LF | L:LOWERCASE_EVEN_HEX_LITERAL_LF)*',
        'identity':'LEGEND_ROOT_AND_ORDER_SCOPED_LOCAL_IDS_NOT_CANONICAL_CSIL',
        'purpose':'HUMAN_INSPECTION_AND_ARCHAIC_INTERCHANGE_NOT_BYTE_OPTIMALITY_OR_SECURITY'},
       'SPP1':{'magic_hex':second_pass.MAGIC.hex(),'grammar':'MAGIC4 || ULEB128(original_count) || ULEB128(output_count) || ULEB128(event_id)*',
        'inverse_roots':['ORIGINAL_PACKED_EVENT_STREAM','SOURCE_BYTES']},
       'XZ_CRYS':{'magic_hex':bytes([253,55,122,88,90,0]).hex(),'grammar':'XZ_PRESET6(EXACT_COMPLETE_EMBEDDED_META_CRYS_WITH_BODY_NONE)',
        'inverse_roots':['EXACT_INNER_ARCHIVE','EXACT_ORIGINAL_ARTIFACTS','DECODED_SOURCES']},
       'SMA1':{'magic_hex':group_legend.BODY_MAGIC.hex(),'grammar':'MAGIC4 || LEGEND_RECIPE_COUNT || RECIPES || ARTIFACT_COUNT || TEMPLATE_SEGMENTS',
        'recipe':'HEADER_BLOB || ORIGINAL_SHA256_32 || ORIGINAL_BYTES_ULEB || ENTRY_COUNT_ULEB || POOL_ID_ULEB*',
        'template':'SEGMENT_COUNT_ULEB || (TAG0_LENGTH_BLOB | TAG1_RECIPE_ID_ULEB)*','inverse_roots':['EXACT_ORIGINAL_ARTIFACTS','DECODED_SOURCES']}
      },
      'instance_variants':rows,
      'terminology':{'group_legend':'HORIZONTAL_EXACT_RECORD_POOL_ACROSS_ARTIFACTS',
       'legacy_metalegend_pack_unpack':'COMPATIBILITY_ALIAS_FOR_GROUP_LEGEND',
       'recursive_metalegend':'VERTICAL_ONE_LEVEL_LEGEND_OF_A_LEGEND_RECIPE'},
      'bindings':{'legend_role_values':['BASE','DELTA','META','ASSEMBLY'],'application_stack_roles':'BASE_THEN_DELTA; META_ARCHIVE_USES_META',
       'placement':['EMBEDDED','EXTERNAL'],'external_resolution':'EXACT_FILE_SHA256_NOT_FILENAME',
       'parent':'EXACT_PRIOR_LEGEND_ROOT','audit_dossier':'SEPARATE_ROOTED_EVIDENCE_NOT_REQUIRED_FOR_BASIC_DECODE'},
      'outer_codec':{'NONE':'UNCHANGED_BODY','LZMA':'FROZEN_DEV73_LZMA2_XZ_PRESET_6_BODY_ONLY',
       'LZMA2_XZ_0':'EXPLICIT_V09_LZMA2_XZ_PRESET_0_BODY_ONLY',
       'LZMA2_XZ_6':'EXPLICIT_V09_LZMA2_XZ_PRESET_6_BODY_ONLY',
       'LZMA2_XZ_9':'EXPLICIT_V09_LZMA2_XZ_PRESET_9_BODY_ONLY',
       'BZ2_1':'EXPLICIT_V09_BZIP2_LEVEL_1_BODY_ONLY','BZ2_9':'EXPLICIT_V09_BZIP2_LEVEL_9_BODY_ONLY',
       'ZSTD':'HELD_OPTIONAL_CODEC_ADAPTER_NOT_PACKAGED','ZSTD_DICT':'HELD_OPTIONAL_CODEC_ADAPTER_NOT_PACKAGED',
       'legend_and_control_compression':'NOT_AUTOMATIC_EXCEPT_EXPLICIT_META_BUNDLE_ENVELOPE',
       'META_BUNDLE':'LZMA2_XZ_PRESET_6_ENTIRE_SELF_CONTAINED_INNER_ARCHIVE','security_claim':'NONE'},
      'codec_selection':{'schema':'semcrys.codec-selection.v0.1','scope':'ONE_EXACT_SOURCE_AND_CONFIGURATION',
       'objective':'MIN_EXACT_COMPLETE_CONTAINER_PLUS_MISSING_DEPENDENCIES','inverse':'REQUIRED_FOR_EVERY_AVAILABLE_CANDIDATE',
       'tie_break':'CALLER_CANDIDATE_ORDER','accounting':['COLD','WARM'],
       'implementation_identity':'APPLICATION_PAYLOAD_PYTHON_RUNTIME_AND_STDLIB_ADAPTERS',
       'future_prediction':False,'global_optimality':False},
      'configuration_selection':{
       'library_schema':'semcrys.legend-stack-library.v0.2','selection_schema':'semcrys.configuration-selection.v0.2',
       'families':['UNION','ULTRA','DOMAIN','SPARSE_EXTENSION','LONGITUDINAL','HYBRID'],
       'family_labels_are_semantic_proof':False,'artifact_accounting':'UNIQUE_ROOT_ONCE',
       'profiles':['C:RAW_BYTES','C:SELF_CONTAINED_TOKEN','T:PRESHARED_TOKEN','A:LONGITUDINAL_TOKEN_DELTA'],
       'objective':'MIN_TOTAL_DELIVERY_BYTES_AT_EXACT_REUSE_HORIZON',
       'tie_break':'CANDIDATE_ID','inverse':'REQUIRED_FOR_EVERY_AVAILABLE_CANDIDATE',
       'accounting':['COLD','WARM'],'future_prediction':False,'global_optimality':False},
      'transport_control':{
       'peer_schema':transport.PEER_SCHEMA,'negotiation_schema':transport.NEGOTIATION_SCHEMA,
       'frame_schema':transport.FRAME_SCHEMA,'pathways':list(transport.PATHWAYS),'codecs':list(transport.CODECS),
       'legend_execution_resolution':'EXACT_ROOT_ONLY','network_stack':False,
       'security_modes':dict(transport.SECURITY_MODES),'security_claim':'NONE'},
      'gtk_adapter':{
       'analysis_schema':gtk_analysis.REPORT_SCHEMA,'decision_schema':gtk_analysis.DECISION_SCHEMA,
       'dossier_schema':gtk_analysis.DOSSIER_SCHEMA,'vocabulary_schema':gtk_analysis.VOCABULARY_SCHEMA,
       'identity_boundary':'GTK_BOUND_TERM_DISTINCT_FROM_LOCAL_TRANSPORT_ID_DISTINCT_FROM_MODEL_TOKEN_ID',
       'source_mutation':False,'canonical_gtk_mutation':False,'security_claim':'NONE'},
      'composition_boundaries':{
       'FORM_WITH_GLYPH_OR_FOLD':'HELD_UNQUALIFIED','FOLD_BASE_NON_TOKEN':'REFUSED',
       'SECOND_PASS_GLYPH_INTEGER_FOLD_OR_ALREADY_COMPOSED':'HELD_UNQUALIFIED',
       'META_EXTERNAL_GLYPH_FOLD_AUXILIARIES':'EXPLICIT_TYPED_EXACT_ROOTS_V02_ARCHIVE_AND_BUNDLE','META_NESTED_ARCHIVE':'HELD_UNQUALIFIED',
       'CRYPTOGRAPHY':'UNAVAILABLE_NOT_INFERRED_FROM_ENCODING','BOUND_GLYPH_SEMANTICS':'HELD_UNQUALIFIED'},
      'resource_limits':{'container_reader':crys_v2.Limits().__dict__,
       'token_unit_bytes':application.MAX_UNIT_BYTES,'form_value_bytes':assembly.MAX_VALUE,'form_depth_exclusive':assembly.MAX_DEPTH,
       'pair_value_bytes':assembly.MAX_PAIR_VALUE,'pair_depth_exclusive':assembly.MAX_PAIR_DEPTH,
       'second_pass_input_bytes':second_pass.MAX_SOURCE,'second_pass_events':second_pass.MAX_EVENTS,
       'group_legend':dict(group_legend.LIMITS),
       'recursive_metalegend':{'max_legend_bytes':recursive_metalegend.MAX_LEGEND_BYTES,
        'max_recipe_bytes':recursive_metalegend.MAX_RECIPE_BYTES,
        'block_entries':[recursive_metalegend.MIN_BLOCK_ENTRIES,recursive_metalegend.MAX_BLOCK_ENTRIES],
        'seekable_frame_blocks':[1,seekable_metalegend.MAX_FRAME_BLOCKS],
        'seekable_frame_recipe_bytes':seekable_metalegend.MAX_FRAME_RECIPE_BYTES,
        'max_depth':1},
       'group_bundle_max_inner_bytes':group_bundle.MAX_INNER,'glyph_bytes':glyph.MAX_BYTES,'glyph_count':glyph.MAX_GLYPHS,
       'limits_are_not_os_peak_certification':True},
      'compatibility_policy':{'application_version_not_format_version':True,'old_bytes_never_rewritten_implicitly':True,
       'legacy_json_legend':'EXPLICIT_MIGRATE_V01','legacy_ordered_legend':'EXPLICIT_IMPORT_ORDERED_V01',
       'legacy_sc_codec':'EXPLICIT_LEGACY_IMPORT_SC_TEXT_V1_V2_AND_SCB1','unknown_configuration':'REFUSE_NOT_GUESS',
       'legacy_scope':'DECODED_BYTE_MIGRATION_NOT_LOCAL_ID_PRESERVATION; EXPLICIT_GLY_AND_SIDECAR; MEMBERS_AND_UNKNOWN_WRAPPERS_HELD'},
      'qualification':'READ_REGRESSION_AND_MATRIX_EVIDENCE; ENUMERATION_IS_NOT_PROOF_OF_EVERY_CROSS_PRODUCT',
      'security_claim':'NONE','admission_effect':'NONE','release_ready':False}
    result['registry_root']=hashlib.sha256(core.canonical(result)).hexdigest()
    return result
