"""SemCrys-A control-profile compiler over the current executable ABI.

The profile layer chooses an existing lossless realization; it does not create
canonical CSIL identities, infer GCNL senses, or provide cryptography.
SPDX-License-Identifier: Apache-2.0
"""
import hashlib
from pathlib import Path

from streaming_app.core import Refusal,compile_funnel
from streaming_legend.core import canonical,file_sha256

SCHEMA='semcrys-a.profile-registry.v0.1'
PLAN_SCHEMA='semcrys-a.configuration-plan.v0.1'
SFTIR_OPERATOR_REGISTRY_ROOT='9ec508560f3634d567f304172452fa6a4200b0297852f6d23873f9b6e24921dd'

ROLES={
 'SELF_CONTAINED_MANUAL':{
  'profile':'C:SELF_CONTAINED_TOKEN','legend_state':'NO_PRIOR_SHARED_STATE; LOCAL_LEGEND_EMBEDDED',
  'minimum_external_legends':0,'maximum_external_legends':0},
 'PENPAL_LONGITUDINAL':{
  'profile':'A:LONGITUDINAL_TOKEN_DELTA','legend_state':'ORDERED_SHARED_HISTORY_PLUS_EMBEDDED_NEW_DELTA',
  'minimum_external_legends':1,'maximum_external_legends':1023},
 'GUILD_PRESHARED':{
  'profile':'T:PRESHARED_TOKEN','legend_state':'EXACT_PRESHARED_GUILD_OR_DOMAIN_STACK',
  'minimum_external_legends':1,'maximum_external_legends':1023},
 'HYBRID_GUILD_LONGITUDINAL':{
  'profile':'A:LONGITUDINAL_TOKEN_DELTA','legend_state':'PRESHARED_BASE_PLUS_ADOPTED_DELTAS_PLUS_EMBEDDED_NEW_DELTA',
  'minimum_external_legends':2,'maximum_external_legends':1023},
}


def _root(value):return hashlib.sha256(canonical(value)).hexdigest()


def registry():
    # Never expose the module's authoritative table by reference to callers.
    result={'schema':SCHEMA,'standing':'CANDIDATE_ONLY','roles':{k:dict(v) for k,v in ROLES.items()},
      'projections':{
       'PACKED':'BYTE_EFFICIENT_LOCAL_EVENT_IDS',
       'INTEGER':'HUMAN_INSPECTABLE_DECIMAL_IDS_AND_HEX_LITERALS',
       'GLYPH':'EXACT_TEMPLATE_REGISTRY_SYMBOL_PROJECTION'},
      'meaning_modes':{'SURFACE':'EXECUTABLE','GCNL_SENSE':'HELD_INJECTABLE_RESOLVER_NOT_PACKAGED'},
      'shuffle_modes':{'NONE':'EXECUTABLE','KEYED_LOCAL_ID_SHUFFLE':'HELD_CRYPTOGRAPHIC_ADAPTER_NOT_PACKAGED'},
      'composition_boundaries':{
       'BODY_FRACTIONATION':'SEPARATE_SECOND_PASS_OPERATION',
       'BATCH_METALEGEND':'SEPARATE_MULTI_DOCUMENT_OPERATION',
       'CROSS_DOCUMENT_BLOBS':'RESEARCH_ONLY_NOT_EQUIVALENT_TO_METALEGEND',
       'LEGEND_RECURSION':'NOT_AUTOMATIC'},
      'sftir':{'operator_registry_root':SFTIR_OPERATOR_REGISTRY_ROOT,
       'addresses':['SFM:SCOPE_BIND','SFM:REFERENCE_RESOLVE','SFM:CURRENT_STATE_SELECT','SFM:IDENTITY_PRESERVE'],
       'role':'EXTERNAL_CONTROL_SEMANTICS_NOT_BYTE_CODEC_OR_IDENTITY'},
      'security_claim':'NONE','canonical_csil_claim':False,'release_effect':'NONE'}
    result['registry_root']=_root(result);return result


def compile_plan(source,*,role,external_legends=(),outer_codec='NONE',projection='PACKED',
                 glyph_registry=None,glyph_placement='EMBEDDED',legend_policy=None,
                 meaning_mode='SURFACE',shuffle_mode='NONE'):
    if role not in ROLES:raise Refusal('HELD_ARCHAIC_ROLE_UNAVAILABLE')
    if meaning_mode!='SURFACE':raise Refusal('HELD_GCNL_RESOLVER_NOT_PACKAGED')
    if shuffle_mode!='NONE':raise Refusal('HELD_KEYED_SHUFFLE_ADAPTER_NOT_PACKAGED')
    legends=tuple(Path(p) for p in external_legends);definition=dict(ROLES[role])
    if not definition['minimum_external_legends']<=len(legends)<=definition['maximum_external_legends']:
        raise Refusal('HELD_ARCHAIC_LEGEND_STATE')
    if role in ('PENPAL_LONGITUDINAL','HYBRID_GUILD_LONGITUDINAL'):
        if legend_policy not in (None,'TOTAL'):raise Refusal('HELD_LONGITUDINAL_REQUIRES_TOTAL_DELTA')
        legend_policy='TOTAL'
    source=Path(source);source_root=file_sha256(source)
    funnel=compile_funnel(source_sha256=source_root,profile=definition['profile'],
      external_legends=legends,outer_codec=outer_codec,legend_policy=legend_policy,
      projection=projection,glyph_registry=glyph_registry,glyph_placement=glyph_placement)
    if file_sha256(source)!=source_root:raise Refusal('HELD_ARCHAIC_SOURCE_CHANGED_DURING_PLAN')
    if [file_sha256(p) for p in legends]!=funnel['instance_constitution']['external_legend_roots']:
        raise Refusal('HELD_ARCHAIC_LEGEND_CHANGED_DURING_PLAN')
    result={'schema':PLAN_SCHEMA,'standing':'CANDIDATE_ONLY','role':role,
      'role_definition':definition,'source_sha256':source_root,
      'legend_roots':funnel['instance_constitution']['external_legend_roots'],
      'projection':projection,'meaning_mode':meaning_mode,'shuffle_mode':shuffle_mode,
      'funnel':funnel,'sftir_control':registry()['sftir'],
      'funnel_instance_state':'REQUESTED_CONFIGURATION_NOT_FINAL_REALIZED_INSTANCE_CONSTITUTION',
      'domain_operation_sequence':['ROOT_SOURCE_AND_LEGENDS','COMPILE_SEMCRYS_A_ROLE',
       'VALIDATE_FUNCTIONAL_CM1','BIND_DESIRABLE_CM2','COMPILE_REQUESTED_CONFIGURATION',
       'REALIZE_THROUGH_CURRENT_APPLICATION','VERIFY_EXACT_INVERSE'],
      'realization_instruction':'USE_ORDINARY_ENCODE_WITH_REQUESTED_FIELDS; FINAL_IC_BINDS_REALIZED_STACK_BODY_AND_WIDTH_OR_ENTRY_COUNTS; RETAIN_ENCODE_RECEIPT',
      'security_claim':'NONE','canonical_csil_claim':False,'authority_effect':'NONE'}
    result['plan_root']=_root(result);return result
