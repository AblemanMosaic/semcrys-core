"""Machine-readable installed CLI contract, derived from the actual parser."""
import argparse
import hashlib
from pathlib import Path
from .integrity import catalogue
from streaming_legend.core import canonical

READ_ONLY_COMMANDS={'fold audit','fold delivery-cost','assembly inspect','recovery inspect','recovery directory-inspect',
 'archaic profiles','archaic plan','transport capabilities','transport negotiate','transport frame','transport verify-frame',
 'gtk capabilities','gtk analyze','gtk verify-vocabulary','workbench status','workbench export',
 'synchronize disclosure','synchronize ordering','synchronize compose','synchronize account',
 'metalegend inspect','metalegend verify','metalegend lookup','list','verify','search','explain-default','help-json'}
READ_ONLY_COMMANDS.add('security inspect');READ_ONLY_COMMANDS.add('security verify')

def _scalar(value):
    if isinstance(value,Path): return str(value)
    if value is argparse.SUPPRESS: return None
    return value

def surface():
    # Imported lazily: the CLI imports this module to dispatch the command.
    from .cli import parser
    commands=[]
    root_parser=parser()
    def visit(node,path):
        children=[a for a in node._actions if isinstance(a,argparse._SubParsersAction)]
        if children:
            for action in children:
                for name,child in sorted(action.choices.items()): visit(child,path+[name])
            return
        arguments=[]
        for action in node._actions:
            if isinstance(action,argparse._HelpAction): continue
            arguments.append({'destination':action.dest,'flags':list(action.option_strings),
                'positional':not bool(action.option_strings),'required':bool(action.required),
                'nargs':action.nargs,'default':_scalar(action.default),'choices':list(action.choices) if action.choices is not None else None,
                'value_type':'boolean' if isinstance(action,(argparse._StoreTrueAction,argparse._StoreFalseAction)) else getattr(action.type,'__name__','string'),
                'repeatable':isinstance(action,argparse._AppendAction)})
        command=' '.join(path)
        commands.append({'semantic_slug':'semcrys.cli.'+'.'.join(path),'command':command,'arguments':arguments,
            'effect':'READ_ONLY' if path[0] in ('verify-self','profiles','capabilities','formats','plan','inspect') or command in READ_ONLY_COMMANDS else 'EXPLICIT_LOCAL_OUTPUT'})
    visit(root_parser,[])
    global_arguments=[]
    for action in root_parser._actions:
        if isinstance(action,(argparse._HelpAction,argparse._SubParsersAction)):continue
        global_arguments.append({'destination':action.dest,'flags':list(action.option_strings),
            'required':bool(action.required),'default':_scalar(action.default),
            'choices':list(action.choices) if action.choices is not None else None,
            'value_type':'boolean' if isinstance(action,(argparse._StoreTrueAction,argparse._StoreFalseAction)) else getattr(action.type,'__name__','string')})
    profiles=catalogue()
    from .formats import registry
    from .release_scope import load as release_scope
    result={'schema':'semcrys.installed-capability-surface.v0.1','standing':'CANDIDATE_ONLY',
        'commands':commands,'global_arguments':global_arguments,'path_first_pack':True,
        'terminal_output':{'stdout':'ONE_JSON_RESULT','stderr':'PROGRESS_PRESENTATION','exit_codes':{'PASS':0,'HELD':1,'CLI_SYNTAX':2,'INTERRUPTED':130}},
        'standard_archive':{'profile':'STANDARD_V1','default_mode':'semantic','full_eligible_local_integerization':True,
            'exact_chunk_deduplication':True,'group_legend_pooling':True,
            'recursive_metalegend':{'available':True,'max_depth':1,'exact_original_legend':True,
                'seekable_frames':True,'direct_integer_lookup':True,
                'verified_frame_cache':True,'verified_full_legend_promotion':True},
            'verified_resumable_cache':True,
            'adaptive_local_and_cross_document_composition':True,
            'composition_admission':'MIN_COMPLETE_SEGMENT_DELIVERY_BYTES',
            'composition_identity_effect':'NONE_TRANSPORT_ONLY',
            'atomic_publication':True,'security_claim':'NONE'},
        'profiles':profiles,'release_scope':release_scope(commands),'abi_registry_root':registry()['registry_root'],'abi_registry_command':'formats',
        'configuration_funnel':{
            'S':'DECLARED_PHASE_SPACE_INCLUDING_EXPLICITLY_UNAVAILABLE_MECHANISMS',
            'CM1':'FUNCTIONAL_PRECONDITIONS_PROFILE_DEPENDENCIES_FORMAT_AND_LIMITS',
            'CM2':'USER_CHOICE_OR_EXACT_SOURCE_MEASURED_COST_NOT_GLOBAL_OPTIMALITY',
            'IC':'ROOTED_EFFECTIVE_CONFIGURATION_BEFORE_REALIZATION',
            'IR':'ACTUAL_REALIZATION_AND_RECONSTRUCTION_RECEIPT'},
        'format_family':{'.crys':'ENCODED_CONTAINER_ABI_0.2_WITH_EXPLICIT_CRITICAL_FEATURES','.leg':'BINARY_LEGEND_ABI_0.2_OR_FOLD_PROJECTION_ABI_0.1_RICH_0.2_COMPACT','.mleg':'ONE_LEVEL_RECURSIVE_METALEGEND_ABI_0.1','.gly':'GLYPH_REGISTRY_ABI_0.1'},
        'admission_effect':'NONE','authority_effect':'NONE','release_ready':False,
        'public_release_authorized':False,'public_release_version':'0.1.0',
        'component_version_note':'Full compiler remains pinned at 0.1.0rc1 inside the authorized 0.1.0 facade',
        'capability_listing_is_not_proof_of_all_option_combinations':True}
    result['surface_root']=hashlib.sha256(canonical(result)).hexdigest()
    return result
