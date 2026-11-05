"""Fixed single-file composite adapters. No arbitrary callable or new root scope.
SPDX-License-Identifier: Apache-2.0
"""
from streaming_app.fold_projection import build_front,extract_front,prefix_front
from .assembly import build,expand
from .local_assembly import encode as local_encode
from .longitudinal_assembly import encode as longitudinal_encode
from .fold_provenance import restore_rich
from .library import select,encode_selected
from .archive import select_archive
from .legacy import migrate as migrate_legacy
from .codec_selection import select as select_codec,encode_selected as encode_selected_codec
from .configuration_selection import select as select_configuration,encode_selected as encode_selected_configuration
from streaming_legend.scratch_budget import ScratchError

def _prefix(source,output,**options):
    return {**prefix_front(source,output,**options),'schema':'semcrys.fold-prefix-result.v0.1'}
def _restore(source,output,**options):
    return {**restore_rich(source,output,**options),'schema':'semcrys.fold-restore-result.v0.1'}
def _expand(source,output,**options):
    return {**expand(source,output,**options),'schema':'semcrys.assembly-expand-result.v0.1'}
def _select(source,output,**options):
    return {**select(source,output,**options),'schema':'semcrys.library-select-result.v0.1'}
def _selected(source,output,*,selection_path,**options):
    return encode_selected(source,selection_path,output,**options)
def _archive(source,output,**options):
    if source is not None:raise ScratchError('HELD_ARCHIVE_SELECT_SOURCE')
    return {**select_archive(output,**options),'schema':'semcrys.archive-select-result.v0.1'}
def _codec_select(source,output,**options):
    return select_codec(source,output,**options)
def _codec_selected(source,output,*,selection_path,**options):
    return encode_selected_codec(source,selection_path,output,**options)
def _configuration_select(source,output,**options):
    return select_configuration(source,output,**options)
def _configuration_selected(source,output,*,selection_path,**options):
    return encode_selected_configuration(source,selection_path,output,**options)

OPERATIONS={
 'FOLD_BUILD':('semcrys.fold-build-result.v0.1',build_front),
 'FOLD_PREFIX':('semcrys.fold-prefix-result.v0.1',_prefix),
 'FOLD_EXTRACT':('semcrys.fold-extraction.v0.1',extract_front),
 'FOLD_RESTORE_RICH':('semcrys.fold-restore-result.v0.1',_restore),
 'ASSEMBLY_BUILD':('semcrys.assembly-build-result.v0.1',build),
 'ASSEMBLY_EXPAND':('semcrys.assembly-expand-result.v0.1',_expand),
 'ASSEMBLY_BUILD_DELTA':('semcrys.assembly-build-result.v0.1',build),
 'ASSEMBLY_ENCODE':('semcrys.local-assembly-selection-result.v0.1',local_encode),
 'ASSEMBLY_ENCODE_LONGITUDINAL':('semcrys.longitudinal-assembly-result.v0.1',longitudinal_encode),
 'SELECT':('semcrys.library-select-result.v0.1',_select),
 'ENCODE_SELECTED':('semcrys.streaming-encode-result.v0.1',_selected),
 'ARCHIVE_SELECT':('semcrys.archive-select-result.v0.1',_archive),
 'CODEC_SELECT':('semcrys.codec-selection-result.v0.1',_codec_select),
 'CODEC_ENCODE_SELECTED':('semcrys.streaming-encode-result.v0.1',_codec_selected),
 'CONFIGURATION_SELECT':('semcrys.configuration-selection-result.v0.2',_configuration_select),
 'CONFIGURATION_ENCODE_SELECTED':('semcrys.streaming-encode-result.v0.1',_configuration_selected),
 'LEGACY_IMPORT':('semcrys.legacy-migration-result.v0.1',migrate_legacy)}
PROGRESS_OPERATIONS={'FOLD_BUILD','ASSEMBLY_ENCODE','ASSEMBLY_ENCODE_LONGITUDINAL','SELECT','ARCHIVE_SELECT','CODEC_SELECT','CODEC_ENCODE_SELECTED','CONFIGURATION_SELECT','CONFIGURATION_ENCODE_SELECTED','LEGACY_IMPORT'}
SCOPE='COMPOSITE_FILE_REALIZATION_AND_ENROLLED_NESTED_IO'
